"""Captura de chat/mensagens do pregoeiro no ComprasNet via API pública + 2captcha.

Descoberta crítica (via HAR file de sessão real): os endpoints autenticados
do ComprasNet são **públicos com hCaptcha** — NÃO precisam de cert digital
nem login. Só do token do 2captcha resolvido.

Endpoints reais (cnetmobile.estaleiro.serpro.gov.br):
  /comprasnet-fase-externa/v1/compras/{cid}/participacao
  /comprasnet-fase-externa/v1/compras/{cid}/em-selecao-fornecedores/itens/{item}/propostas
  /comprasnet-mensagem/v2/chat/{cid}/itens/{item}?size=10&page=N&legadoAsp=false&captcha=TOKEN

`cid` = formato 17 chars: UASG(6) + MOD(2) + NUM(5) + ANO(4)
Ex: 982913-3-90005-2026 → 98291303900052026

Token captcha tem validade ~2min do 2captcha + reuso depende do SERPRO
(observado ~25min antes de expirar).

Categorias de mensagem (categoria):
  8  = convocação do pregoeiro (URGENTE, exige resposta)
  14 = mensagem de fornecedor
  outras = consultar TIPO_CATEGORIA quando descobrir mais
tipoRemetente: "0" = pregoeiro, "1" = fornecedor
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

log = logging.getLogger("radar.comprasnet.chat")

BASE = "https://cnetmobile.estaleiro.serpro.gov.br"
# Endpoints REAIS descobertos via HAR do site público (2026-05-22). NÃO usar `/public/v1/`!
# Funcionam sem cookies/cert, só com headers padrão (x-device-platform, referer) — chat exige captcha.
URL_PARTICIPACAO = f"{BASE}/comprasnet-fase-externa/v1/compras/{{cid}}/participacao"
URL_PROPOSTAS = f"{BASE}/comprasnet-fase-externa/v1/compras/{{cid}}/em-selecao-fornecedores/itens/{{item}}/propostas?ordenacao-propostas=V"
URL_ITENS_FILTRO = f"{BASE}/comprasnet-fase-externa/v1/sistema/compras/{{cid}}/mensagens/itens-para-filtro?captcha={{captcha}}"
URL_CHAT = f"{BASE}/comprasnet-mensagem/v2/chat/{{cid}}/itens/{{item}}?size={{size}}&page={{page}}&legadoAsp=false&incluirMensagensCompra=true&captcha={{captcha}}"
URL_CAPTCHA_CONFIG = f"{BASE}/comprasnet-fase-externa/v1/captcha/configuracao"

# hCaptcha sitekey (descoberta: hardcoded, mesmo pra todos os tenants)
HCAPTCHA_SITEKEY = "b8bbded1-9d04-4ace-9952-b67cde081a7b"
HCAPTCHA_PAGE_URL = f"{BASE}/comprasnet-web/public/compras/acompanhamento-compra"

# Token reusa por ~25min (observado)
TOKEN_TTL_SEG = 22 * 60

_CAPTCHA_CACHE: dict[str, tuple[str, float]] = {}  # key='global', value=(token, fetched_at)
_CAPTCHA_LOCK = asyncio.Lock()

# Cache do CID resolvido por pregão: key=input compra_id, value=(cid_17chars, fetched_at)
# Evita iterar 8 modalidades toda hora pro mesmo pregão.
_CID_RESOLVIDO: dict[str, tuple[str, float]] = {}
CID_RESOLVIDO_TTL = 24 * 3600  # 24h — modalidade não muda

# Backoff global em 429 — pausa todo o módulo se SERPRO bater rate limit
_BACKOFF_UNTIL: float = 0.0

CATEGORIA_LABEL = {
    "1": "info",
    "8": "convocacao_documentacao",
    "9": "mensagem_pregoeiro",
    "14": "mensagem_fornecedor",
}

# tipoRemetente observado nas APIs do ComprasNet:
# "0" = pregoeiro (sistema/operação) — convocações, atos automáticos
# "1" = fornecedor (mensagens de licitante)
# "3" = pregoeiro (chat textual da sessão) — quem está conduzindo o pregão
# Default: assume fornecedor pra IDs desconhecidos (mais seguro pra não atribuir mensagem errada ao pregoeiro)
TIPO_REMETENTE_PREGOEIRO = {"0", "3"}

# Headers padrão — espelho do HAR do browser real (2026-05-19) pra não levar 403 por fingerprint
HEADERS_PADRAO = {
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "bloqueio-desabilitado": "true",
    "cache-control": "no-cache, no-store, max-age=0, must-revalidate",
    "expires": "0",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "x-device-platform": "web",
    "x-version-number": "6.0.2",
    "referer": f"{BASE}/comprasnet-web/seguro/fornecedor/acompanhamento-compra/item/1",
    "origin": BASE,
}


def _referer_pregao(cid: str, item: int = 1) -> str:
    """Referer espelha o site real: /acompanhamento-compra/item/N?compra=CID."""
    return f"{BASE}/comprasnet-web/seguro/fornecedor/acompanhamento-compra/item/{item}?compra={cid}"


def _twocaptcha_key() -> str | None:
    return os.environ.get("TWOCAPTCHA_API_KEY")


def _formatar_compra_id(uasg: str, modalidade: int, numero: str, ano: int) -> str:
    """Formato ComprasNet: UASG(6) + MOD(2) + NUM(5) + ANO(4) = 17 chars."""
    return f"{str(uasg).zfill(6)}{str(modalidade).zfill(2)}{str(numero).zfill(5)}{str(ano).zfill(4)}"


def parsear_compra_id(compra_id: str) -> tuple[str, int, str, int]:
    """Reverso: 17 chars OU 'UASG-MOD-NUM-ANO' OU 'UASG-NUM-ANO' (MOD=0)."""
    if "-" in compra_id:
        parts = compra_id.split("-")
        if len(parts) == 4:
            return parts[0], int(parts[1]), parts[2], int(parts[3])
        if len(parts) == 3:
            # Sem modalidade — devolve 0 (caller pode iterar candidatos)
            return parts[0], 0, parts[1], int(parts[2])
    # Tem que ter EXATO 17 chars sem hífen pra ser formato compactado
    if len(compra_id) == 17 and "-" not in compra_id and compra_id.isdigit():
        return (
            compra_id[0:6].lstrip("0"),
            int(compra_id[6:8]),
            compra_id[8:13].lstrip("0") or "0",
            int(compra_id[13:17]),
        )
    raise ValueError(f"compra_id inválido: {compra_id}")


# Modalidades válidas a tentar quando MOD=0 (ordem por frequência de pregões em sessão)
MODS_FALLBACK = [5, 6, 4, 3, 20, 7, 1, 2]


def _gerar_cids_candidatos(compra_id: str) -> list[str]:
    """Quando MOD=0, gera lista de CIDs possíveis pra tentar. Se já resolvemos antes, usa cache."""
    cached = _CID_RESOLVIDO.get(compra_id)
    if cached and (time.time() - cached[1]) < CID_RESOLVIDO_TTL:
        return [cached[0]]
    try:
        uasg, mod, num, ano = parsear_compra_id(compra_id)
    except ValueError:
        return []
    if mod != 0:
        return [_formatar_compra_id(uasg, mod, num, ano)]
    return [_formatar_compra_id(uasg, m, num, ano) for m in MODS_FALLBACK]


def _registrar_cid_resolvido(compra_id_original: str, cid_que_funcionou: str) -> None:
    """Memoriza qual MOD funcionou pra esse pregão — próximas chamadas vão direto."""
    _CID_RESOLVIDO[compra_id_original] = (cid_que_funcionou, time.time())
    log.info(f"cid resolvido cacheado: {compra_id_original} → {cid_que_funcionou}")


def _normalizar_compra_id(compra_id: str) -> str:
    """Aceita 'UASG-MOD-NUM-ANO', 'UASG-NUM-ANO', ou 17 chars compactos. Default MOD=0 quando não vier."""
    if "-" in compra_id:
        uasg, mod, num, ano = parsear_compra_id(compra_id)
        return _formatar_compra_id(uasg, mod, num, ano)
    return compra_id


async def _resolver_hcaptcha() -> str | None:
    """Resolve hCaptcha priorizando solver LOCAL (R$ 0). Fallback 2captcha se local falhar.

    Provider: env RADAR_CAPTCHA_PROVIDER = 'local' | '2captcha' | 'auto' (default).
    Em 'auto', tenta local primeiro, depois 2captcha.

    LOCK GLOBAL — garante que só 1 solver roda por vez (evita brigas pelo chromedriver).
    """
    # Lock global pra TODO o processo de resolver — incluindo o solve em si
    async with _CAPTCHA_LOCK:
        cached = _CAPTCHA_CACHE.get("global")
        if cached and (time.monotonic() - cached[1]) < TOKEN_TTL_SEG:
            log.info("usando token captcha cacheado")
            return cached[0]

        # Vai resolver — chamadores subsequentes vão pegar do cache depois
        provider = os.environ.get("RADAR_CAPTCHA_PROVIDER", "auto").lower()
        return await _resolver_inner(provider)


async def _resolver_inner(provider: str) -> str | None:
    """Chamado já dentro de _CAPTCHA_LOCK — não pode usar o lock de novo (deadlock)."""

    # Tenta LOCAL primeiro (R$ 0)
    if provider in ("local", "auto"):
        try:
            from radar.adapters.hcaptcha_local import solve_hcaptcha_local
            log.info("resolvendo hCaptcha LOCAL (R$ 0, 9-25s)...")
            token = await solve_hcaptcha_local(max_attempts=2)
            if token and len(token) > 50:
                log.info(f"local OK — token len={len(token)}")
                _CAPTCHA_CACHE["global"] = (token, time.monotonic())  # já tá no lock
                return token
            log.warning("solver local não retornou token, vai tentar 2captcha")
        except ImportError as e:
            log.warning(f"solver local indisponível: {e}")
        except Exception as e:
            log.exception(f"erro no solver local: {e}")

        if provider == "local":
            log.error("provider=local mas solver falhou — abortando (sem fallback)")
            return None

    # Fallback 2captcha
    from radar.adapters import _captcha_state
    if not _captcha_state.ativo():
        log.warning("2captcha kill-switch ativo (saldo zero) — não tenta fallback")
        return None

    api_key = _twocaptcha_key()
    if not api_key:
        log.error("TWOCAPTCHA_API_KEY não configurada e solver local falhou")
        return None

    try:
        from twocaptcha import TwoCaptcha
    except ImportError:
        log.error("2captcha-python não instalado")
        return None

    log.info("2captcha resolvendo hCaptcha (fallback, 15-60s, R$ 0,06)…")
    solver = TwoCaptcha(api_key, defaultTimeout=120, pollingInterval=5)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: solver.hcaptcha(sitekey=HCAPTCHA_SITEKEY, url=HCAPTCHA_PAGE_URL),
        )
        token = result.get("code")
        log.info(f"2captcha OK — token len={len(token or '')}")
        _CAPTCHA_CACHE["global"] = (token, time.monotonic())  # já tá no lock
        return token
    except Exception as e:
        if _captcha_state.eh_erro_saldo_zero(e):
            _captcha_state.desativar_por_saldo_zero(f"chat: {e}")
            return None
        log.exception(f"2captcha falhou: {e}")
        return None


async def _request(client: httpx.AsyncClient, url: str, retry_captcha: bool = True) -> httpx.Response | None:
    global _BACKOFF_UNTIL
    # Respeita backoff de 429 — pausa antes de mandar
    agora = time.monotonic()
    if agora < _BACKOFF_UNTIL:
        wait = _BACKOFF_UNTIL - agora
        log.info(f"backoff 429 ativo — aguardando {wait:.1f}s antes de prosseguir")
        await asyncio.sleep(wait)
    try:
        r = await client.get(url, headers=HEADERS_PADRAO)
    except httpx.HTTPError as e:
        log.warning(f"erro de rede em {url[:120]}: {e}")
        return None
    if r.status_code == 429:
        # Rate limit — backoff global de 30s, devolve a response pra caller decidir
        retry_after = r.headers.get("retry-after")
        try:
            wait_s = float(retry_after) if retry_after else 30.0
        except ValueError:
            wait_s = 30.0
        wait_s = min(wait_s, 60.0)
        _BACKOFF_UNTIL = time.monotonic() + wait_s
        log.warning(f"SERPRO 429 — backoff global ativo por {wait_s:.0f}s")
        return r
    if r.status_code in (401, 403):
        # Capturar corpo pra diagnosticar (SERPRO costuma mandar mensagem)
        try:
            body = r.text[:400]
        except Exception:
            body = "(sem corpo)"
        log.warning(f"SERPRO {r.status_code} em {url[:80]} → corpo: {body}")
        if retry_captcha:
            log.info("invalidando cache de captcha e tentando 1x com token fresco")
            async with _CAPTCHA_LOCK:
                _CAPTCHA_CACHE.pop("global", None)
            # Resolve novo token e refaz URL (substitui captcha=... no querystring)
            novo_token = await _resolver_hcaptcha()
            if not novo_token:
                return None
            import re as _re
            url2 = _re.sub(r"captcha=[^&]+", f"captcha={novo_token}", url)
            try:
                r2 = await client.get(url2, headers=HEADERS_PADRAO)
            except httpx.HTTPError as e:
                log.warning(f"retry erro de rede: {e}")
                return None
            if r2.status_code in (401, 403):
                try:
                    body2 = r2.text[:400]
                except Exception:
                    body2 = "(sem corpo)"
                log.error(f"SERPRO {r2.status_code} mesmo com captcha fresco → corpo: {body2}")
                return r2
            return r2
        return r
    return r


async def fetch_participacao(compra_id: str) -> dict | None:
    """Retorna info da compra (público, sem captcha — site usa esse endpoint pra abrir a tela)."""
    cid = _normalizar_compra_id(compra_id)
    async with httpx.AsyncClient(timeout=15) as client:
        url = URL_PARTICIPACAO.format(cid=cid)
        hdrs = {**HEADERS_PADRAO, "referer": _referer_pregao(cid)}
        try:
            r = await client.get(url, headers=hdrs)
        except httpx.HTTPError as e:
            log.warning(f"participacao erro: {e}")
            return None
        if r.status_code != 200:
            return None
        try: return r.json()
        except Exception: return None


async def _resolver_cid_no_client(compra_id: str, client: httpx.AsyncClient, token: str) -> str | None:
    """Resolve CID usando um httpx.Client EXISTENTE (compartilha cookies de sessão).
    SERPRO rejeita 2ª request com token se cookies de sessão são novos."""
    cached = _CID_RESOLVIDO.get(compra_id)
    if cached and (time.time() - cached[1]) < CID_RESOLVIDO_TTL:
        return cached[0]
    cids = _gerar_cids_candidatos(compra_id)
    if not cids:
        return None
    if len(cids) == 1:
        _registrar_cid_resolvido(compra_id, cids[0])
        return cids[0]
    for idx, cid in enumerate(cids):
        if idx > 0:
            await asyncio.sleep(0.3)
        hdrs = {**HEADERS_PADRAO, "referer": _referer_pregao(cid)}
        url = URL_CHAT.format(cid=cid, item=1, size=1, page=0, captcha=token)
        try:
            r = await client.get(url, headers=hdrs)
        except httpx.HTTPError:
            continue
        # 200/206 = CID válido com dados; 204 = pode ser CID válido vazio ou CID errado
        # Prefere 200/206 — só aceita 204 se for último candidato
        if r.status_code in (200, 206):
            _registrar_cid_resolvido(compra_id, cid)
            return cid
    # Fallback: nenhum retornou 200/206 — usa o primeiro candidato que não deu 404
    return cids[0]


async def _resolver_cid(compra_id: str) -> str | None:
    """Versão standalone (cria próprio client). Usar só fora de fetch_chat."""
    token = await _resolver_hcaptcha()
    if not token:
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        return await _resolver_cid_no_client(compra_id, client, token)


async def fetch_itens_para_filtro(cid: str) -> list[int]:
    """Lista de itens do pregão que TÊM mensagens. Site público usa pra montar filtros."""
    token = await _resolver_hcaptcha()
    if not token:
        return []
    url = URL_ITENS_FILTRO.format(cid=cid, captcha=token)
    hdrs = {**HEADERS_PADRAO, "referer": _referer_pregao(cid)}
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(url, headers=hdrs)
        except httpx.HTTPError as e:
            log.warning(f"itens-para-filtro erro: {e}")
            return []
        if r.status_code != 200:
            log.info(f"itens-para-filtro cid={cid} HTTP {r.status_code} (sem itens com chat)")
            return []
        try:
            data = r.json()
        except Exception:
            return []
        # Schema: [{"codigo":"1","descricao":"..."}, ...]
        itens = []
        for entry in data:
            cod = entry.get("codigo") or entry.get("item") or entry.get("numero")
            try:
                itens.append(int(cod))
            except (TypeError, ValueError):
                pass
        log.info(f"itens com mensagens cid={cid}: {itens}")
        return itens


async def fetch_propostas_item(compra_id: str, item: int = 1) -> list[dict]:
    """Retorna propostas/lances do item. Endpoint público — sem captcha, só headers."""
    cid = await _resolver_cid(compra_id)
    if not cid:
        return []
    hdrs = {**HEADERS_PADRAO, "referer": _referer_pregao(cid, item)}
    async with httpx.AsyncClient(timeout=20) as client:
        url = URL_PROPOSTAS.format(cid=cid, item=item)
        try:
            r = await client.get(url, headers=hdrs)
        except httpx.HTTPError as e:
            log.warning(f"propostas erro: {e}")
            return []
        if r.status_code in (200, 206):
            try:
                data = r.json()
                result = data if isinstance(data, list) else (data.get("propostas") or data.get("resultado") or [])
                if result:
                    log.info(f"propostas OK cid={cid} item={item} qtd={len(result)}")
                return result or []
            except Exception:
                return []
        if r.status_code != 204:
            log.warning(f"propostas cid={cid} item={item} HTTP {r.status_code}")
    return []


async def fetch_chat(
    compra_id: str, item: int | None = None, page_size: int = 50, max_pages: int = 5,
    itens_a_tentar: int = 5,
) -> list[dict]:
    """Retorna TODAS as mensagens do pregão.

    Fluxo (igual ao site público):
    1. Resolve CID dentro do MESMO httpx.Client (cookies persistem — SERPRO exige)
    2. Itera itens 1..N — pra cada um, pagina o chat
    3. 404 num item = pregão não tem aquele item → para
    4. 204 = item existe mas sem msgs → pula
    5. 200 = msgs! agrega

    Se `item` for passado, foca só nele (compat).
    """
    token = await _resolver_hcaptcha()
    if not token:
        return []

    # Resolve CID — se já no cache, vai direto. Se não, itera candidates COM size=50
    # (não faz request "probe" separado que invalida o token no SERPRO).
    cached_cid = _CID_RESOLVIDO.get(compra_id)
    if cached_cid and (time.time() - cached_cid[1]) < CID_RESOLVIDO_TTL:
        cids_a_tentar = [cached_cid[0]]
    else:
        cids_a_tentar = _gerar_cids_candidatos(compra_id)
    if not cids_a_tentar:
        return []

    todas: list[dict] = []
    async with httpx.AsyncClient(timeout=20) as client:
        # Tenta cada CID candidate fazendo fetch real (size=50 do item 1).
        # O 1º que retornar 200/206 com dados é o CID válido.
        cid = None
        for idx_cid, cid_tentativa in enumerate(cids_a_tentar):
            if cid is not None:
                break
            if idx_cid > 0:
                await asyncio.sleep(0.3)
            hdrs = {**HEADERS_PADRAO, "referer": _referer_pregao(cid_tentativa, 1)}
            url = URL_CHAT.format(cid=cid_tentativa, item=1, size=page_size, page=0, captcha=token)
            try:
                r = await client.get(url, headers=hdrs)
            except httpx.HTTPError:
                continue
            if r.status_code in (200, 206):
                try:
                    batch = r.json()
                except Exception:
                    continue
                if isinstance(batch, list):
                    cid = cid_tentativa
                    _registrar_cid_resolvido(compra_id, cid)
                    if batch:
                        todas.extend(batch)
                        log.info(f"chat cid={cid} item=1 p0 +{len(batch)} msgs (HTTP {r.status_code})")
                    break
            elif r.status_code == 204:
                # CID provavelmente válido mas item 1 vazio. Marca como possível.
                if len(cids_a_tentar) == 1:
                    cid = cid_tentativa
        if not cid:
            return todas
        if item is not None:
            itens = [item]
        else:
            itens = list(range(2, itens_a_tentar + 1))  # item 1 já consumido acima
        for idx_item, n_item in enumerate(itens):
            if idx_item > 0:
                await asyncio.sleep(0.3)
            hdrs = {**HEADERS_PADRAO, "referer": _referer_pregao(cid, n_item)}
            for page in range(max_pages):
                url = URL_CHAT.format(cid=cid, item=n_item, size=page_size, page=page, captcha=token)
                try:
                    r = await client.get(url, headers=hdrs)
                except httpx.HTTPError as e:
                    log.warning(f"chat erro {cid}/it{n_item} p{page}: {e}")
                    break
                if r.status_code == 429:
                    log.warning(f"chat 429 cid={cid} — abortando")
                    return todas
                if r.status_code in (401, 403):
                    # Captcha expirou — renova e tenta de novo
                    log.info(f"chat {r.status_code} — renovando captcha")
                    async with _CAPTCHA_LOCK:
                        _CAPTCHA_CACHE.pop("global", None)
                    token = await _resolver_hcaptcha()
                    if not token:
                        return todas
                    continue
                if r.status_code == 204:
                    log.info(f"chat cid={cid} item={n_item} 204 (vazio)")
                    break  # item sem msgs — vai pro próximo item
                if r.status_code == 404:
                    # item não existe → pregão tem menos itens; sai do loop principal
                    log.info(f"chat cid={cid} item={n_item} 404 — fim dos itens (total={len(todas)})")
                    return todas
                if r.status_code not in (200, 206):
                    log.warning(f"chat cid={cid} item={n_item} p{page} HTTP {r.status_code} body={r.text[:200]}")
                    break
                try:
                    batch = r.json()
                except Exception as e:
                    log.warning(f"chat cid={cid} item={n_item} p{page} JSON err: {e}")
                    break
                if not batch or not isinstance(batch, list):
                    log.info(f"chat cid={cid} item={n_item} p{page} batch vazio (type={type(batch).__name__})")
                    break
                log.info(f"chat cid={cid} item={n_item} p{page} +{len(batch)} msgs (HTTP {r.status_code})")
                todas.extend(batch)
                if len(batch) < page_size:
                    break
    if todas:
        log.info(f"chat OK cid={cid} total_msgs={len(todas)} itens={itens}")
    return todas


def normalizar_mensagens(raw: list[dict]) -> list[dict]:
    """Normaliza shape pro detector de eventos do radar."""
    out = []
    for m in raw:
        cat = str(m.get("categoria") or "")
        tipo_remetente = str(m.get("tipoRemetente") or "")
        remetente = "pregoeiro" if tipo_remetente in TIPO_REMETENTE_PREGOEIRO else "fornecedor"
        out.append({
            "id": m.get("chaveMensagemNaOrigem") or m.get("id"),
            "remetente": remetente,
            "texto": m.get("texto") or "",
            "horario": m.get("dataHora"),
            "categoria": cat,
            "categoria_label": CATEGORIA_LABEL.get(cat, f"categoria_{cat}"),
            "destinatario_cnpj": m.get("identificadorDestinatario"),
            "remetente_cnpj": m.get("identificadorRemetente"),
            "raw": m,
        })
    return out


def normalizar_propostas(raw: list[dict], cnpj_proprio: str | None = None) -> tuple[list[dict], int | None, float | None, float | None, str | None]:
    """Retorna (lances normalizados, minha_pos, meu_lance, melhor_geral, melhor_cnpj)."""
    out = []
    for i, l in enumerate(sorted(raw, key=lambda x: float(x.get("valorLance") or x.get("valor") or 0))):
        out.append({
            "id": l.get("identificadorProposta") or l.get("id"),
            "posicao": i + 1,
            "cnpj": l.get("cnpjFornecedor") or l.get("cnpj"),
            "empresa": l.get("razaoSocial") or l.get("nomeFornecedor"),
            "valor": l.get("valorLance") or l.get("valor"),
            "horario": l.get("dataHoraLance") or l.get("dataHora"),
        })

    minha_pos = None
    meu_lance = None
    if cnpj_proprio:
        cnpj_norm = "".join(filter(str.isdigit, cnpj_proprio))
        for l in out:
            if "".join(filter(str.isdigit, l.get("cnpj") or "")) == cnpj_norm:
                minha_pos = l["posicao"]
                meu_lance = l["valor"]
                break

    melhor = out[0]["valor"] if out else None
    melhor_cnpj = out[0].get("cnpj") if out else None
    return out, minha_pos, meu_lance, melhor, melhor_cnpj


async def fetch_live(
    compra_id: str, cnpj_proprio: str | None = None, item: int | None = None,
) -> dict | None:
    """Wrapper completo: chat (todos os itens com msgs) + propostas. Sem cert."""
    chat_raw, propostas_raw = await asyncio.gather(
        fetch_chat(compra_id, item=item),
        fetch_propostas_item(compra_id, item=item or 1),
    )
    mensagens = normalizar_mensagens(chat_raw)
    lances, minha_pos, meu_lance, melhor, melhor_cnpj = normalizar_propostas(propostas_raw, cnpj_proprio)
    return {
        "lances": lances,
        "mensagens": mensagens,
        "minha_posicao": minha_pos,
        "meu_melhor_lance": meu_lance,
        "melhor_lance": melhor,
        "melhor_lance_cnpj": melhor_cnpj,
        "fase": None,  # será inferida pela API pública via classificador
    }


def captcha_status() -> dict:
    return {
        "configured": bool(_twocaptcha_key()),
        "provider": "2captcha" if _twocaptcha_key() else None,
        "cached_token": "global" in _CAPTCHA_CACHE,
    }
