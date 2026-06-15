"""Autenticação ComprasNet via certificado digital A1 (.pfx) + 2captcha.

Fluxo completo (igual eLicita, Effecti & cia):
  1. Playwright abre browser headless com client_certificates (mTLS)
  2. Navega pra comprasnet.gov.br/seguro/loginPortalUASG.asp
  3. Clica perfil "Fornecedor Brasileiro" (mudaPerfilBotao(1))
  4. Clica "Entrar com Gov.br" → redirect pra sso.acesso.gov.br
  5. Clica "Seu certificado digital" → dispara hCaptcha
  6. 2captcha resolve o hCaptcha (15-30s)
  7. Token injetado, form submetido
  8. Browser segue redirects com cert mTLS
  9. Cookies capturados, retornados pra reuso em httpx

Cache de sessão por tenant. Renova quando expira (~25min).

Requer: TWOCAPTCHA_API_KEY no .env (cadastre em https://2captcha.com).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("radar.comprasnet.pfx")

BASE_CNET = "https://cnetmobile.estaleiro.serpro.gov.br"
URL_LOGIN_ASP = "https://www.comprasnet.gov.br/seguro/loginPortalUASG.asp"
# URLs REAIS descobertas via HAR (browser logado). compra_id no formato 17 chars: UASG(6)+MOD(2)+NUM(5)+ANO(4)
URL_PARTICIPACAO_TPL = f"{BASE_CNET}/comprasnet-fase-externa/v1/compras/{{cid}}/participacao"
URL_ITENS_SELECAO_TPL = f"{BASE_CNET}/comprasnet-fase-externa/v1/compras/{{cid}}/itens/em-selecao-fornecedores"
URL_PROPOSTAS_PROPRIAS_TPL = f"{BASE_CNET}/comprasnet-fase-externa/v1/compras/{{cid}}/em-selecao-fornecedores/participacoes/{{cnpj}}/itens/{{item}}/propostas?filtro=1"
URL_CHAT_TPL = f"{BASE_CNET}/comprasnet-mensagem/v2/chat/{{cid}}/itens/{{item}}?size=50&page=0&legadoAsp=false"

# Sessão renovada SÓ por 401/403 real, NÃO por timer arbitrário.
# Antes era 25min hardcoded → queimava captcha sem necessidade.
SESSION_TTL_MAX_SEG = 6 * 3600  # safety net: força renovação após 6h máx (caso lifecycle bug)

# Cap diário de solves de 2captcha — controle de custo
# Acima desse limite por tenant em 24h, pausa por 24h e exige intervenção manual
CAP_DIARIO_SOLVES = int(os.environ.get("CAPTCHA_CAP_DIARIO_TENANT", "15"))
CUSTO_POR_SOLVE_BRL = 0.06  # estimativa 2captcha hCaptcha ~US$ 0,012 * cot 5

# Circuit breaker: após N solves resultarem em 403 do SERPRO (IP banido), pausa
CIRCUIT_BREAKER_LIMIAR = 3
CIRCUIT_BREAKER_PAUSA_SEG = 1800  # 30min

_PW: Any = None
_BROWSER: Any = None
_BROWSER_LOCK = asyncio.Lock()
_SESSION_CACHE: dict[int, dict] = {}
_SESSION_LOCKS: dict[int, asyncio.Lock] = {}

# Cache de pregões onde o cert do tenant NÃO tem permissão (403 fresco — não é não-autenticado).
# Evita loop de re-login que queima 2captcha. TTL 1h: cert continua igual, permissão também.
_PFX_SEM_PERMISSAO: dict[tuple[int, str], float] = {}  # (tenant_id, compra_id) -> ts
PFX_SEM_PERMISSAO_TTL = 3600


def _registrar_custo(tenant_id: int, evento: str, valor: float = 0.0, detalhe: str = "") -> None:
    """Registra cada solve/falha pra dashboard de custo."""
    try:
        from shared.database import get_db
        get_db().execute(
            "INSERT INTO radar_custo_captcha (tenant_id, evento, valor_brl, detalhe) VALUES (?, ?, ?, ?)",
            (tenant_id, evento, valor, detalhe[:200] if detalhe else None),
        )
        get_db().commit()
    except Exception as e:
        log.warning(f"falha ao registrar custo captcha: {e}")


def _solves_hoje(tenant_id: int) -> int:
    """Conta solves OK do tenant nas últimas 24h."""
    try:
        from shared.database import get_db
        r = get_db().execute(
            "SELECT COUNT(*) FROM radar_custo_captcha "
            "WHERE tenant_id = ? AND evento = 'solve_ok' "
            "AND criado_em > datetime('now', '-1 day')",
            (tenant_id,),
        ).fetchone()
        return r[0] if r else 0
    except Exception:
        return 0


def _circuit_breaker_ativo(tenant_id: int) -> bool:
    """Verifica se tenant tá pausado por IP-ban suspeito."""
    try:
        from shared.database import get_db
        r = get_db().execute(
            "SELECT bloqueado_ate FROM radar_circuit_breaker "
            "WHERE tenant_id = ? AND bloqueado_ate > datetime('now')",
            (tenant_id,),
        ).fetchone()
        return r is not None
    except Exception:
        return False


def _circuit_breaker_falha(tenant_id: int, erro: str) -> None:
    """Incrementa contador. Após N seguidas, pausa por 30min."""
    from shared.database import get_db
    conn = get_db()
    cur = conn.execute(
        "SELECT falhas_consecutivas FROM radar_circuit_breaker WHERE tenant_id = ?",
        (tenant_id,),
    ).fetchone()
    n_atual = (cur[0] if cur else 0) + 1
    bloqueio = None
    if n_atual >= CIRCUIT_BREAKER_LIMIAR:
        from datetime import datetime, timedelta
        # Formato compatível com SQLite datetime('now') — espaço, não T
        bloqueio = (datetime.now() + timedelta(seconds=CIRCUIT_BREAKER_PAUSA_SEG)).strftime("%Y-%m-%d %H:%M:%S")
        log.warning(f"[tenant={tenant_id}] CIRCUIT BREAKER ativado: {n_atual} falhas — pausado até {bloqueio}")
        _registrar_custo(tenant_id, "ip_banido", 0, erro[:200])
    conn.execute(
        """INSERT INTO radar_circuit_breaker (tenant_id, portal_slug, falhas_consecutivas, bloqueado_ate, ultimo_erro, atualizado_em)
           VALUES (?, 'comprasnet', ?, ?, ?, datetime('now'))
           ON CONFLICT(tenant_id) DO UPDATE SET
             falhas_consecutivas = excluded.falhas_consecutivas,
             bloqueado_ate = excluded.bloqueado_ate,
             ultimo_erro = excluded.ultimo_erro,
             atualizado_em = excluded.atualizado_em""",
        (tenant_id, n_atual, bloqueio, erro[:200]),
    )
    conn.commit()


def _circuit_breaker_sucesso(tenant_id: int) -> None:
    """Reseta contador após login bem-sucedido."""
    try:
        from shared.database import get_db
        get_db().execute(
            "UPDATE radar_circuit_breaker SET falhas_consecutivas = 0, bloqueado_ate = NULL WHERE tenant_id = ?",
            (tenant_id,),
        )
        get_db().commit()
    except Exception:
        pass


def _twocaptcha_key() -> str | None:
    return os.environ.get("TWOCAPTCHA_API_KEY")


def _origins_para_cert() -> list[str]:
    return [
        "https://www.comprasnet.gov.br",
        "https://comprasnet.gov.br",
        "https://cnetmobile.estaleiro.serpro.gov.br",
        "https://sso.acesso.gov.br",
        "https://certificado.sso.acesso.gov.br",  # CRÍTICO: valida cert mTLS aqui!
        "https://www.gov.br",
        "https://gov.br",
        "https://acesso.gov.br",
        "https://www.acesso.gov.br",
        "https://contas.acesso.gov.br",
        "https://login.acesso.gov.br",
        "https://certificado.acesso.gov.br",
        "https://signin.acesso.gov.br",
    ]


async def _ensure_browser():
    global _PW, _BROWSER
    async with _BROWSER_LOCK:
        if _BROWSER is not None:
            try:
                if _BROWSER.is_connected():
                    return _BROWSER
            except Exception:
                pass
        from playwright.async_api import async_playwright
        _PW = await async_playwright().start()
        launch_kwargs = dict(
            headless=True,
            args=[
                "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--ignore-certificate-errors",
            ],
        )
        proxy = _proxy_config()
        if proxy:
            # Playwright proxy format: {"server": "http://host:port", "username": "...", "password": "..."}
            from urllib.parse import urlparse
            up = urlparse(proxy)
            launch_kwargs["proxy"] = {
                "server": f"{up.scheme}://{up.hostname}:{up.port}",
                **({"username": up.username, "password": up.password} if up.username else {}),
            }
            log.info(f"Playwright usando proxy {up.scheme}://{up.hostname}:{up.port}")
        _BROWSER = await _PW.chromium.launch(**launch_kwargs)
        log.info("Playwright Chromium iniciado (singleton)")
        return _BROWSER


async def encerrar_browser():
    global _BROWSER, _PW, _SESSION_CACHE
    _SESSION_CACHE.clear()
    if _BROWSER is not None:
        try: await _BROWSER.close()
        except Exception: pass
        _BROWSER = None
    if _PW is not None:
        try: await _PW.stop()
        except Exception: pass
        _PW = None


async def _resolver_hcaptcha(sitekey: str, page_url: str, tenant_id: int = 0) -> str | None:
    """Resolve hCaptcha via 2captcha COM controles de custo:
    - Hard cap: N solves/dia/tenant (env CAPTCHA_CAP_DIARIO_TENANT)
    - Circuit breaker: pausa após 3 falhas consecutivas (IP banido provável)
    - Log de cada solve/falha em radar_custo_captcha
    """
    # 0. Kill-switch global (saldo zero detectado em outra chamada)
    from radar.adapters import _captcha_state
    if not _captcha_state.ativo():
        log.warning(f"[tenant={tenant_id}] 2captcha kill-switch ATIVO (saldo zero) — pulando")
        if tenant_id:
            _registrar_custo(tenant_id, "solve_falhou", 0, "kill-switch saldo zero")
        return None

    # 1. Circuit breaker (IP banido?)
    if tenant_id and _circuit_breaker_ativo(tenant_id):
        log.warning(f"[tenant={tenant_id}] circuit breaker ATIVO — não solve captcha (suspeita IP ban)")
        return None

    # 2. Cap diário
    if tenant_id:
        usados = _solves_hoje(tenant_id)
        if usados >= CAP_DIARIO_SOLVES:
            log.error(f"[tenant={tenant_id}] CAP DIÁRIO atingido: {usados}/{CAP_DIARIO_SOLVES} solves. Pausando 2captcha por 24h.")
            _registrar_custo(tenant_id, "cap_excedido", 0, f"{usados} solves/dia")
            return None
        log.info(f"[tenant={tenant_id}] solves hoje: {usados}/{CAP_DIARIO_SOLVES}")

    api_key = _twocaptcha_key()
    if not api_key:
        log.error("TWOCAPTCHA_API_KEY não configurada — não dá pra resolver hCaptcha")
        if tenant_id:
            _registrar_custo(tenant_id, "solve_falhou", 0, "sem api key")
        return None

    try:
        from twocaptcha import TwoCaptcha
    except ImportError:
        log.error("biblioteca 2captcha-python não instalada")
        return None

    log.info(f"2captcha resolvendo hCaptcha sitekey={sitekey[:12]}... (15-60s)")
    solver = TwoCaptcha(api_key, defaultTimeout=120, pollingInterval=5)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: solver.hcaptcha(sitekey=sitekey, url=page_url),
        )
        token = result.get("code")
        captcha_id = result.get("captchaId", "?")
        log.info(f"2captcha OK em {captcha_id} — token len={len(token or '')}")
        if tenant_id:
            _registrar_custo(tenant_id, "solve_ok", CUSTO_POR_SOLVE_BRL, f"id={captcha_id}")
        return token
    except Exception as e:
        if _captcha_state.eh_erro_saldo_zero(e):
            _captcha_state.desativar_por_saldo_zero(f"pfx tenant={tenant_id}: {e}")
            if tenant_id:
                _registrar_custo(tenant_id, "solve_falhou", 0, "saldo zero (kill-switch)")
            return None
        log.exception(f"2captcha falhou: {e}")
        if tenant_id:
            _registrar_custo(tenant_id, "solve_falhou", 0, str(e)[:200])
        return None


async def _safe_query(page, selector: str, max_tries: int = 15, espera_ms: int = 1500):
    """query_selector tolerante a navegações concorrentes."""
    for _ in range(max_tries):
        try:
            el = await page.query_selector(selector)
            if el:
                return el
        except Exception as e:
            # Execution context destroyed por navegação — espera e tenta de novo
            if "Execution context was destroyed" in str(e) or "context" in str(e).lower():
                pass
            else:
                log.warning(f"query_selector {selector} erro: {e}")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        await page.wait_for_timeout(espera_ms)
    return None


async def _safe_evaluate(page, script: str, *args, max_tries: int = 10, espera_ms: int = 1500):
    """evaluate tolerante a navegação."""
    for _ in range(max_tries):
        try:
            return await page.evaluate(script, *args) if args else await page.evaluate(script)
        except Exception as e:
            if "Execution context was destroyed" in str(e) or "context" in str(e).lower():
                pass
            else:
                log.warning(f"evaluate erro: {e}")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        await page.wait_for_timeout(espera_ms)
    return None


async def _detectar_hcaptcha_sitekey(page) -> str | None:
    """Procura sitekey do hCaptcha na página atual (tolerante a navegações)."""
    # Esperar página estabilizar antes de procurar
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass
    await page.wait_for_timeout(2000)
    try:
        sitekey = await page.evaluate(r"""() => {
            // 1. h-captcha div
            const div = document.querySelector('[data-sitekey]');
            if (div) return div.getAttribute('data-sitekey');
            // 2. hcaptcha iframe
            const iframe = document.querySelector('iframe[src*="hcaptcha.com"][src*="sitekey"]');
            if (iframe) {
                const m = iframe.src.match(/sitekey=([a-f0-9-]+)/);
                if (m) return m[1];
            }
            // 3. script inline
            const scripts = Array.from(document.querySelectorAll('script')).map(s => s.textContent || '');
            for (const s of scripts) {
                const m = s.match(/sitekey['"\s:=]+([0-9a-f-]{36})/);
                if (m) return m[1];
            }
            return null;
        }""")
        return sitekey
    except Exception as e:
        log.warning(f"falha ao detectar sitekey: {e}")
        return None


async def _injetar_token_hcaptcha(page, token: str) -> bool:
    """Injeta token resolvido nos campos do hCaptcha + dispara callback."""
    try:
        injetou = await page.evaluate(f"""(token) => {{
            // Popula todos os campos h-captcha-response
            const inputs = document.querySelectorAll('[name="h-captcha-response"], [name="g-recaptcha-response"]');
            inputs.forEach(i => {{ i.value = token; i.innerHTML = token; }});
            // Tenta executar callback registrado
            if (window.hcaptcha && typeof window.hcaptcha.execute === 'function') {{
                // nada — só seta valor
            }}
            // Dispara evento change
            inputs.forEach(i => {{
                i.dispatchEvent(new Event('input', {{ bubbles: true }}));
                i.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }});
            return inputs.length;
        }}""", token)
        log.info(f"token injetado em {injetou} campo(s)")
        return injetou > 0
    except Exception as e:
        log.warning(f"falha ao injetar token: {e}")
        return False


async def _criar_sessao_autenticada(
    tenant_id: int, pfx_bytes: bytes, senha: str,
) -> dict | None:
    """Fluxo completo de login com cert + hCaptcha via 2captcha."""
    pfx_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pfx").name
    Path(pfx_path).write_bytes(pfx_bytes)

    browser = await _ensure_browser()
    try:
        ctx = await browser.new_context(
            client_certificates=[
                {"origin": origin, "pfxPath": pfx_path, "passphrase": senha}
                for origin in _origins_para_cert()
            ],
            ignore_https_errors=True,
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120 Safari/537.36"
            ),
        )
        try:
            page = await ctx.new_page()

            # Intercepta requests pra descobrir como app SPA autentica APIs cnetmobile
            api_requests_capturadas: list[dict] = []
            def _capturar_request(req):
                u = req.url
                if "cnetmobile" in u and ("/v1/" in u or "/v2/" in u or "/api/" in u):
                    # Filtra só requests potencialmente úteis
                    auth_hdr = req.headers.get("authorization", "")
                    if auth_hdr or "compras/" in u or "chat/" in u or "participacao" in u:
                        api_requests_capturadas.append({
                            "method": req.method,
                            "url": u,
                            "auth": auth_hdr[:80] if auth_hdr else "",
                            "headers": {k: v for k, v in req.headers.items()
                                        if k.lower() in ("authorization", "x-auth-token", "x-api-key", "x-csrf-token", "x-session-id", "x-access-token")},
                        })
            page.on("request", _capturar_request)

            # === 1. Login ASP page ===
            log.info(f"[tenant={tenant_id}] step 1: loginPortalUASG.asp")
            await page.goto(URL_LOGIN_ASP, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # === 2. Selecionar perfil Fornecedor Brasileiro ===
            log.info(f"[tenant={tenant_id}] step 2: mudaPerfilBotao(1)")
            # Espera a função estar disponível (race condition com JS load)
            for tentativa in range(10):
                tem = await page.evaluate("typeof mudaPerfilBotao === 'function'")
                if tem:
                    break
                await page.wait_for_timeout(1000)
            await page.evaluate("mudaPerfilBotao(1)")
            await page.wait_for_timeout(1500)

            # === 3. Clicar Entrar com Gov.br ===
            log.info(f"[tenant={tenant_id}] step 3: Entrar com Gov.br")
            btn = await _safe_query(page, 'button:has-text("Entrar com Gov.br")', max_tries=8)
            if not btn:
                log.error("botão Entrar com Gov.br não encontrado")
                return None
            try:
                async with page.expect_navigation(timeout=30000):
                    await btn.click()
            except Exception as e:
                log.warning(f"navegação Gov.br: {e}")
            try: await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception: pass
            await page.wait_for_timeout(3000)

            # === 4. Clicar Seu certificado digital ===
            log.info(f"[tenant={tenant_id}] step 4: clicando #login-certificate")
            cert_btn = await _safe_query(page, '#login-certificate', max_tries=15, espera_ms=2000)
            if not cert_btn:
                # Tenta seletores alternativos do gov.br atualizado
                for sel in ['button[id*="certificate"]', 'a[href*="certificado"]', 'button:has-text("certificado")', 'a:has-text("certificado")']:
                    cert_btn = await _safe_query(page, sel, max_tries=3, espera_ms=1000)
                    if cert_btn:
                        log.info(f"  achou via seletor alternativo: {sel}")
                        break
            if not cert_btn:
                log.error("botão de certificado digital não encontrado em gov.br")
                try:
                    titulo = await page.title()
                    url = page.url
                    log.error(f"  página atual: {url} | título: {titulo}")
                except Exception:
                    pass
                return None
            # Click submeta o form pra certificado.sso.acesso.gov.br (exige cert mTLS)
            try:
                async with page.expect_navigation(timeout=30000):
                    await cert_btn.click()
            except Exception as e:
                log.info(f"navegação cert: {e}")
            await page.wait_for_timeout(5000)
            log.info(f"[tenant={tenant_id}] após cert submit: {page.url[:120]}")

            # === 5. hCaptcha aparece — resolver na própria page (R$ 0) com fallback 2captcha ===
            log.info(f"[tenant={tenant_id}] step 5: detectando hCaptcha sitekey")
            sitekey = await _detectar_hcaptcha_sitekey(page)
            if sitekey:
                log.info(f"[tenant={tenant_id}] hCaptcha sitekey={sitekey[:12]}...")

                # 5a. Tenta resolver invisível na própria page (sem custo)
                try:
                    from radar.adapters.hcaptcha_local import solve_on_playwright_page
                    token = await solve_on_playwright_page(page, sitekey_esperada=sitekey, timeout_seg=30)
                except ImportError:
                    token = None

                # 5b. Fallback 2captcha (somente se kill-switch e cap permitirem)
                if not token:
                    log.info(f"[tenant={tenant_id}] solve local falhou — tentando 2captcha fallback")
                    page_url_atual = page.url
                    token = await _resolver_hcaptcha(sitekey, page_url_atual, tenant_id=tenant_id)

                if not token:
                    log.error("hCaptcha não resolvido (local + 2captcha falharam)")
                    return None
                injetado = await _injetar_token_hcaptcha(page, token)
                if not injetado:
                    log.error("falha ao injetar token hCaptcha")
                    return None

                # === 6. Submeter form pós-captcha ===
                log.info(f"[tenant={tenant_id}] step 6: submetendo form pós-captcha")
                # Procura botão submit/continuar OU dispara callback do hCaptcha
                submetido = await page.evaluate("""() => {
                    // Tenta callback global do hCaptcha
                    if (window.onHcaptchaSuccess) { try { window.onHcaptchaSuccess(arguments[0]); return 'callback'; } catch(e){} }
                    // Procura form e submete
                    const forms = document.querySelectorAll('form');
                    for (const f of forms) {
                        if (f.querySelector('[name="h-captcha-response"]')) {
                            f.submit();
                            return 'form-submit';
                        }
                    }
                    // Procura botão Continuar/Entrar
                    const btns = Array.from(document.querySelectorAll('button, input[type=submit]'));
                    for (const b of btns) {
                        const t = (b.textContent || b.value || '').toLowerCase();
                        if (t.includes('continuar') || t.includes('entrar')) {
                            b.click();
                            return 'btn-click';
                        }
                    }
                    return 'no-action';
                }""")
                log.info(f"[tenant={tenant_id}] pós-captcha ação: {submetido}")
                try: await page.wait_for_load_state("networkidle", timeout=30000)
                except Exception: pass
                await page.wait_for_timeout(8000)
            else:
                log.info(f"[tenant={tenant_id}] sem hCaptcha — seguindo direto")
                await page.wait_for_timeout(8000)

            # === 7. Aguardar redirects naturais ===
            for _ in range(6):
                url = page.url
                if "cnetmobile" in url:
                    break
                if "acesso.gov.br" in url or "comprasnet.gov.br" in url:
                    await page.wait_for_timeout(2500)
                    continue
                break

            # === 8. Forçar navegação pro cnetmobile pra estabelecer cookie SSO ===
            if "cnetmobile" not in page.url:
                log.info(f"[tenant={tenant_id}] step 8: forçando nav pro cnetmobile (estava em {page.url[:80]})")
                try:
                    await page.goto(
                        f"{BASE_CNET}/comprasnet-web/seguro/fornecedor/painel-fornecedor",
                        wait_until="domcontentloaded", timeout=30000,
                    )
                    await page.wait_for_timeout(8000)
                except Exception as e:
                    log.warning(f"nav forçada falhou: {e}")
                # Tenta outras variações se essa não funcionar
                if "acesso-nao-autorizado" in page.url or "pagina-nao-encontrada" in page.url:
                    for tentativa in [
                        f"{BASE_CNET}/comprasnet-web/seguro/painel-fornecedor",
                        f"{BASE_CNET}/comprasnet-web/seguro/area-trabalho",
                        f"{BASE_CNET}/comprasnet-web/",
                    ]:
                        try:
                            await page.goto(tentativa, wait_until="domcontentloaded", timeout=15000)
                            await page.wait_for_timeout(3000)
                            if "acesso-nao-autorizado" not in page.url and "pagina-nao-encontrada" not in page.url:
                                log.info(f"[tenant={tenant_id}] cnetmobile entrou em: {page.url[:100]}")
                                break
                        except Exception:
                            continue

            # === 9. Visitar um pregão pra disparar requests autenticadas reais ===
            # CRAS Delamare Japeri = compra que sabemos que existe
            try:
                pregao_test_url = f"{BASE_CNET}/comprasnet-web/seguro/fornecedor/acompanhamento-compra?compra=98291303900052026"
                log.info(f"[tenant={tenant_id}] step 9: visitando pregão pra disparar APIs autenticadas")
                await page.goto(pregao_test_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(8000)  # tempo pro SPA fazer chamadas
            except Exception as e:
                log.warning(f"[tenant={tenant_id}] falha visitando pregão teste: {e}")

            # Log das requests autenticadas capturadas
            if api_requests_capturadas:
                log.info(f"[tenant={tenant_id}] === API REQUESTS CAPTURADAS NO BROWSER ({len(api_requests_capturadas)}) ===")
                for req in api_requests_capturadas[:15]:
                    log.info(f"  {req['method']} {req['url'][:100]}")
                    if req["headers"]:
                        log.info(f"     headers: {req['headers']}")
            else:
                log.warning(f"[tenant={tenant_id}] NENHUMA request /v1/ ou /v2/ capturada durante login+pregão")

            final_url = page.url
            log.info(f"[tenant={tenant_id}] URL final: {final_url}")

            cookies = await ctx.cookies()
            cookies_cnet = [c for c in cookies if "cnetmobile" in (c.get("domain") or "") or "estaleiro" in (c.get("domain") or "")]
            log.info(f"[tenant={tenant_id}] cookies: total={len(cookies)} cnetmobile={len(cookies_cnet)}")

            # CAPTURA localStorage + sessionStorage — onde apps SPA guardam JWT/auth tokens
            try:
                local_storage = await page.evaluate("""() => {
                    const out = {};
                    try {
                        for (let i = 0; i < localStorage.length; i++) {
                            const k = localStorage.key(i);
                            out[k] = localStorage.getItem(k);
                        }
                    } catch (e) {}
                    return out;
                }""")
                session_storage = await page.evaluate("""() => {
                    const out = {};
                    try {
                        for (let i = 0; i < sessionStorage.length; i++) {
                            const k = sessionStorage.key(i);
                            out[k] = sessionStorage.getItem(k);
                        }
                    } catch (e) {}
                    return out;
                }""")
            except Exception as e:
                log.warning(f"[tenant={tenant_id}] falha capturando storage: {e}")
                local_storage = {}
                session_storage = {}

            log.info(f"[tenant={tenant_id}] localStorage keys: {list(local_storage.keys())}")
            log.info(f"[tenant={tenant_id}] sessionStorage keys: {list(session_storage.keys())}")

            # Procura tokens (JWT) em qualquer storage — heurística pelos nomes comuns
            token_candidates = {}
            for storage_name, storage in [("localStorage", local_storage), ("sessionStorage", session_storage)]:
                for k, v in storage.items():
                    if any(needle in k.lower() for needle in ["token", "jwt", "auth", "session", "access"]):
                        token_candidates[f"{storage_name}.{k}"] = (v[:60] + "..." if v and len(v) > 60 else v)
                    elif v and len(v) > 30 and (v.startswith("eyJ") or v.startswith("Bearer ")):
                        # JWT começa com "eyJ" (base64 do JSON header)
                        token_candidates[f"{storage_name}.{k}"] = v[:60] + "..."
            if token_candidates:
                log.info(f"[tenant={tenant_id}] TOKENS encontrados:")
                for k, v in token_candidates.items():
                    log.info(f"  {k}: {v}")
            else:
                log.warning(f"[tenant={tenant_id}] NENHUM token JWT encontrado em storage")

            return {
                "cookies": cookies,
                "local_storage": local_storage,
                "session_storage": session_storage,
                "final_url": final_url,
                "fetched_at": time.monotonic(),
            }
        finally:
            await ctx.close()
    finally:
        try: Path(pfx_path).unlink()
        except OSError: pass


def _carregar_sessao_persistida(tenant_id: int) -> dict | None:
    """Carrega cookies salvos do banco. Evita relogin a cada restart do servidor."""
    try:
        from shared.database import get_db
        from radar.credenciais import decifrar_dict
        r = get_db().execute(
            "SELECT extra_cifrado FROM credenciais_portal c "
            "JOIN portais po ON po.id = c.portal_id "
            "WHERE c.tenant_id = ? AND po.slug = 'comprasnet'",
            (tenant_id,),
        ).fetchone()
        if not r:
            return None
        extra = decifrar_dict(r["extra_cifrado"]) or {}
        sess = extra.get("_sessao_cache")
        if not sess:
            return None
        idade = time.time() - sess.get("fetched_at_real", 0)
        if idade > SESSION_TTL_MAX_SEG:
            log.info(f"[tenant={tenant_id}] sessão persistida expirada ({int(idade)}s)")
            return None
        log.info(f"[tenant={tenant_id}] sessão persistida válida (idade={int(idade)}s) — REUSANDO sem login")
        return {
            "cookies": sess["cookies"],
            "final_url": sess.get("final_url", ""),
            "fetched_at": time.monotonic(),  # marca como recente em monotonic
        }
    except Exception as e:
        log.warning(f"falha ao carregar sessão persistida: {e}")
        return None


def _persistir_sessao(tenant_id: int, sessao: dict) -> None:
    """Salva cookies cifrados no banco pra sobreviver restart do servidor."""
    try:
        from shared.database import get_db
        from radar.credenciais import decifrar_dict, cifrar_dict
        conn = get_db()
        r = conn.execute(
            "SELECT c.extra_cifrado FROM credenciais_portal c "
            "JOIN portais po ON po.id = c.portal_id "
            "WHERE c.tenant_id = ? AND po.slug = 'comprasnet'",
            (tenant_id,),
        ).fetchone()
        if not r:
            return
        extra = decifrar_dict(r["extra_cifrado"]) or {}
        extra["_sessao_cache"] = {
            "cookies": sessao.get("cookies", []),
            "final_url": sessao.get("final_url", ""),
            "fetched_at_real": time.time(),
        }
        conn.execute(
            "UPDATE credenciais_portal SET extra_cifrado = ? "
            "WHERE tenant_id = ? AND portal_id IN (SELECT id FROM portais WHERE slug = 'comprasnet')",
            (cifrar_dict(extra), tenant_id),
        )
        conn.commit()
        log.info(f"[tenant={tenant_id}] sessão persistida no banco — sobrevive restart")
    except Exception as e:
        log.warning(f"falha ao persistir sessão: {e}")


async def obter_sessao_autenticada(
    tenant_id: int, pfx_b64: str, senha: str, forcar: bool = False,
) -> dict | None:
    """Sessão cacheada indefinidamente — em memória E no banco.
    Renova SÓ quando:
    - `forcar=True` (chamado em 401/403)
    - Safety net: passou SESSION_TTL_MAX_SEG (6h) sem uso
    """
    if _circuit_breaker_ativo(tenant_id):
        log.warning(f"[tenant={tenant_id}] sessão NÃO criada — circuit breaker ativo")
        return None

    lock = _SESSION_LOCKS.setdefault(tenant_id, asyncio.Lock())
    async with lock:
        cached = _SESSION_CACHE.get(tenant_id)
        if not forcar and cached:
            idade = time.monotonic() - cached["fetched_at"]
            if idade < SESSION_TTL_MAX_SEG:
                return cached
            log.info(f"[tenant={tenant_id}] sessão em memória > 6h (safety net), renovando")

        # Tenta carregar do banco antes de fazer login novo (economia de captcha)
        if not forcar:
            persistida = _carregar_sessao_persistida(tenant_id)
            if persistida:
                _SESSION_CACHE[tenant_id] = persistida
                return persistida

        try:
            pfx_bytes = base64.b64decode(pfx_b64)
        except Exception as e:
            log.error(f"pfx_b64 inválido: {e}")
            return None

        # Timeout absoluto: garante cleanup do ctx mesmo em deadlock de Playwright.
        # Sem isso, um Chrome zumbi com cert pode segurar ~300 MB indefinidamente.
        try:
            sessao = await asyncio.wait_for(
                _criar_sessao_autenticada(tenant_id, pfx_bytes, senha),
                timeout=120,
            )
        except asyncio.TimeoutError:
            log.error(f"[tenant={tenant_id}] _criar_sessao_autenticada timeout 120s — forçando cleanup")
            sessao = None
        if sessao:
            _SESSION_CACHE[tenant_id] = sessao
            _persistir_sessao(tenant_id, sessao)
            _circuit_breaker_sucesso(tenant_id)
        else:
            _circuit_breaker_falha(tenant_id, "falha ao criar sessão (cert/captcha/IP)")
        return sessao


def _cookies_para_httpx(sessao: dict) -> dict[str, str]:
    # Inclui cookies de cnetmobile + serpro (cross-domain)
    return {c["name"]: c["value"] for c in sessao.get("cookies", [])
            if any(d in (c.get("domain") or "") for d in ["cnetmobile", "estaleiro", "serpro"])}


def _proxy_config() -> str | None:
    """Lê RADAR_PROXY_URL do env. Formato: http://user:pass@host:port (ou socks5://)."""
    return os.environ.get("RADAR_PROXY_URL") or None


async def _request_autenticado(sessao: dict, url: str) -> httpx.Response | None:
    cookies = _cookies_para_httpx(sessao)
    if not cookies:
        return None
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36",
        "Origin": BASE_CNET,
        "Referer": f"{BASE_CNET}/comprasnet-web/",
        "X-Requested-With": "XMLHttpRequest",
    }
    proxy = _proxy_config()
    client_kwargs = dict(timeout=15, cookies=cookies, headers=headers, follow_redirects=False)
    if proxy:
        client_kwargs["proxy"] = proxy
    async with httpx.AsyncClient(**client_kwargs) as client:
        try:
            return await client.get(url)
        except httpx.HTTPError as e:
            log.warning(f"erro de rede em {url}: {e}")
            return None


def _normalizar_cid_17(compra_id: str, mod_override: int | None = None) -> str | None:
    """Formato 17 chars: UASG(6)+MOD(2)+NUM(5)+ANO(4). Aceita 'UASG-MOD-NUM-ANO' ou 'UASG-NUM-ANO' (MOD=0)."""
    if "-" not in compra_id:
        return compra_id if len(compra_id) == 17 else None
    parts = compra_id.split("-")
    if len(parts) == 4:
        uasg, mod, num, ano = parts
    elif len(parts) == 3:
        uasg, num, ano = parts
        mod = "0"
    else:
        return None
    if mod_override is not None:
        mod = str(mod_override)
    try:
        return f"{int(uasg):06d}{int(mod):02d}{int(num):05d}{int(ano):04d}"
    except ValueError:
        return None


# Modalidades válidas no ComprasNet (ordem de tentativa quando MOD=0)
MODS_TENTAR = [5, 6, 4, 3, 20, 7, 1, 2]


def _gerar_cids_candidatos(compra_id: str) -> list[str]:
    """Quando MOD=0, tenta várias modalidades possíveis."""
    cid = _normalizar_cid_17(compra_id)
    if not cid:
        return []
    # Se MOD não-zero, retorna só ele
    mod_atual = int(cid[6:8])
    if mod_atual != 0:
        return [cid]
    # MOD=0 → gera versões com MODs comuns
    return [_normalizar_cid_17(compra_id, mod_override=m) for m in MODS_TENTAR if _normalizar_cid_17(compra_id, mod_override=m)]


async def fetch_acompanhamento(sessao: dict, compra_id: str) -> dict | None:
    """Pega participação + itens em seleção (= status real do pregão).
    Quando MOD=0 (não especificado pelo user), tenta várias modalidades até achar 200.
    """
    cids = _gerar_cids_candidatos(compra_id)
    if not cids:
        log.warning(f"compra_id inválido pra normalização: {compra_id}")
        return None

    auth_expired = False
    for cid in cids:
        url = URL_PARTICIPACAO_TPL.format(cid=cid)
        r = await _request_autenticado(sessao, url)
        if not r:
            continue
        if r.status_code == 200:
            log.info(f"participacao {cid} OK (mod={int(cid[6:8])})")
            try:
                data = r.json() if r.text else None
                if data is not None:
                    # Inclui CID resolvido pra uso posterior em fetch_mensagens
                    if isinstance(data, dict):
                        data["_cid_resolvido"] = cid
                    return data
            except json.JSONDecodeError:
                continue
        elif r.status_code in (401, 403):
            auth_expired = True
            # 403 com MOD certo = problema de sessão (não modalidade); aborta sem tentar outras
            if int(cid[6:8]) != 0 and len(cids) == 1:
                break
            # Senão, continua tentando outras modalidades — pode ser MOD errado
            continue
        else:
            log.warning(f"participacao {cid} HTTP {r.status_code}: {r.text[:200]}")

    if auth_expired:
        return {"_auth_expired": True}
    return None


async def fetch_mensagens(sessao: dict, compra_id: str, item: int = 1, cid_resolvido: str | None = None) -> list[dict]:
    """Pega chat do pregoeiro com fornecedor.
    Endpoint /v2/chat/{cid}/itens/{item} com cookies de sessão.
    Se cid_resolvido já foi descoberto via /participacao, usa ele (evita tentar várias MODs).
    """
    cids = [cid_resolvido] if cid_resolvido else _gerar_cids_candidatos(compra_id)
    if not cids:
        return []

    for cid in cids:
        url = URL_CHAT_TPL.format(cid=cid, item=item)
        r = await _request_autenticado(sessao, url)
        if not r:
            continue
        if r.status_code in (200, 206):
            try:
                data = r.json() if r.text else []
            except json.JSONDecodeError:
                continue
            msgs = data if isinstance(data, list) else (data.get("mensagens") or data.get("itens") or data.get("content") or [])
            if msgs or len(cids) == 1:
                log.info(f"chat {cid}/item{item}: {len(msgs)} msgs")
                return _normalizar_mensagens(msgs)
        elif r.status_code == 204:
            # 204 = sem mensagens (mas endpoint válido) — pode ser que esse MOD seja o certo
            if len(cids) == 1:
                return []
        else:
            log.warning(f"chat {cid}/item{item} HTTP {r.status_code}: {r.text[:120]}")
    return []


async def fetch_propostas_proprias(sessao: dict, compra_id: str, cnpj: str, item: int = 1) -> list[dict]:
    """Pega propostas/lances do CNPJ próprio. Sem captcha (cookie de sessão basta)."""
    cid = _normalizar_cid_17(compra_id)
    cnpj_limpo = "".join(filter(str.isdigit, cnpj or ""))
    if not cid or not cnpj_limpo:
        return []
    url = URL_PROPOSTAS_PROPRIAS_TPL.format(cid=cid, cnpj=cnpj_limpo, item=item)
    r = await _request_autenticado(sessao, url)
    if not r or r.status_code != 200:
        return []
    try:
        data = r.json() if r.text else []
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


CATEGORIA_LABEL = {
    "1": "info",
    "8": "convocacao_documentacao",
    "14": "mensagem_fornecedor",
}


def _normalizar_mensagens(raw: list[dict]) -> list[dict]:
    """Normaliza mensagens do endpoint /v2/chat conforme formato real (HAR):
    tipoRemetente: '0'=pregoeiro, '1'=fornecedor
    categoria: '8'=convocação doc (urgente), '14'=mensagem normal
    """
    out = []
    for m in raw:
        # Formato novo (v2/chat)
        tipo_rem = str(m.get("tipoRemetente", ""))
        remetente_kind = "fornecedor" if tipo_rem == "1" else "pregoeiro"
        categoria = str(m.get("categoria") or m.get("tipo") or "")
        cat_label = CATEGORIA_LABEL.get(categoria, categoria or "info")
        out.append({
            "id": m.get("chaveMensagemNaOrigem") or m.get("id") or m.get("seqMensagem"),
            "remetente": remetente_kind,
            "texto": m.get("texto") or m.get("mensagem") or m.get("descricao") or "",
            "horario": m.get("dataHora") or m.get("dataEnvio") or m.get("horario"),
            "categoria": categoria,
            "categoria_label": cat_label,
            "destinatario_cnpj": m.get("identificadorRemetente") or m.get("destinatarioCnpj"),
        })
    # Ordenar do mais novo pro mais velho (API às vezes vem fora de ordem)
    out.sort(key=lambda x: (x.get("horario") or ""), reverse=True)
    return out


def _normalizar_lances(acompanhamento: dict | None) -> list[dict]:
    if not acompanhamento:
        return []
    raw = (
        acompanhamento.get("lances")
        or acompanhamento.get("classificacao")
        or acompanhamento.get("propostas")
        or []
    )
    out = []
    for i, l in enumerate(raw):
        out.append({
            "id": l.get("id") or l.get("seqLance"),
            "posicao": l.get("posicao") or l.get("classificacao") or (i + 1),
            "cnpj": l.get("cnpj") or l.get("cnpjFornecedor"),
            "empresa": l.get("razaoSocial") or l.get("fornecedor") or l.get("empresa"),
            "valor": l.get("valor") or l.get("valorLance") or l.get("valorProposta"),
            "horario": l.get("dataHora") or l.get("horario"),
        })
    return out


def extrair_fase(acompanhamento: dict | None) -> str | None:
    if not acompanhamento:
        return None
    s = str(acompanhamento.get("faseAtual") or acompanhamento.get("fase") or acompanhamento.get("situacaoFase") or "").lower()
    if not s:
        return None
    pares = [("homolog","homologacao"),("adjudic","adjudicacao"),("habilit","habilitacao"),("negocia","negociacao"),("lance","lances"),("propost","propostas")]
    for needle, fase in pares:
        if needle in s:
            return fase
    return None


def extrair_posicao_propria(acompanhamento: dict | None, cnpj_proprio: str | None) -> tuple[int | None, float | None]:
    if not acompanhamento or not cnpj_proprio:
        return None, None
    cnpj_norm = "".join(filter(str.isdigit, cnpj_proprio))
    for l in _normalizar_lances(acompanhamento):
        cnpj = "".join(filter(str.isdigit, l.get("cnpj") or ""))
        if cnpj == cnpj_norm:
            return l.get("posicao"), l.get("valor")
    return None, None


async def fetch_live_pfx(
    tenant_id: int, pfx_b64: str, senha: str, compra_id: str, cnpj_proprio: str | None = None,
) -> dict | None:
    # Curto-circuito: pregão já marcado como "cert sem permissão" (403 fresco)
    chave = (tenant_id, compra_id)
    marca = _PFX_SEM_PERMISSAO.get(chave)
    if marca and (time.time() - marca) < PFX_SEM_PERMISSAO_TTL:
        log.info(f"[tenant={tenant_id}] cert sem permissão pra {compra_id} (cache), pulando pfx")
        return None

    sessao = await obter_sessao_autenticada(tenant_id, pfx_b64, senha)
    if not sessao:
        return None

    acomp = await fetch_acompanhamento(sessao, compra_id)
    if acomp and acomp.get("_auth_expired"):
        # 403 com sessão RECÉM criada (<5min) = cert sem permissão pra esse pregão,
        # NÃO sessão expirada. Marca e desiste — re-login não vai resolver.
        sess_age = time.time() - (sessao.get("fetched_at_real") or 0)
        if sess_age < 300:
            log.warning(f"[tenant={tenant_id}] 403 com sessão fresca ({int(sess_age)}s) — cert não-participante de {compra_id}")
            _PFX_SEM_PERMISSAO[chave] = time.time()
            return None
        sessao = await obter_sessao_autenticada(tenant_id, pfx_b64, senha, forcar=True)
        if sessao:
            acomp = await fetch_acompanhamento(sessao, compra_id)
            if acomp and acomp.get("_auth_expired"):
                # Mesmo após relogin volta 403 → cert sem permissão
                _PFX_SEM_PERMISSAO[chave] = time.time()
                return None
        else:
            acomp = None

    cid_resolvido = (acomp or {}).get("_cid_resolvido") if isinstance(acomp, dict) else None
    msgs = await fetch_mensagens(sessao, compra_id, cid_resolvido=cid_resolvido) if sessao else []
    lances = _normalizar_lances(acomp)
    fase = extrair_fase(acomp)
    minha_pos, meu_lance = extrair_posicao_propria(acomp, cnpj_proprio)
    melhor = None
    melhor_cnpj = None
    if lances:
        ordenados = sorted([l for l in lances if l.get("valor") is not None], key=lambda x: x["valor"])
        if ordenados:
            melhor = ordenados[0].get("valor")
            melhor_cnpj = ordenados[0].get("cnpj")

    return {
        "lances": lances,
        "mensagens": msgs,
        "fase": fase,
        "minha_posicao": minha_pos,
        "meu_melhor_lance": meu_lance,
        "melhor_lance": melhor,
        "melhor_lance_cnpj": melhor_cnpj,
    }


def captcha_status() -> dict:
    """Pra UI/API exibir se 2captcha tá configurado."""
    return {
        "configured": bool(_twocaptcha_key()),
        "provider": "2captcha" if _twocaptcha_key() else None,
    }
