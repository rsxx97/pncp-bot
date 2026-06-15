"""Resolução LOCAL de hCaptcha SERPRO usando undetected-chromedriver.

Adaptado de https://github.com/gustavoSilvaAlves/Portal-ComprasGOV (MIT).

Vantagens vs 2captcha:
- Custo R$ 0 (não paga solver humano)
- Mais rápido (~15-25s vs 60-120s do 2captcha)
- Independente de saldo/cap externo

Desvantagens:
- Requer Chrome instalado + RAM (~200 MB por solve)
- Pode quebrar se hCaptcha mudar detecção
- Concorrência limitada (1-5 paralelos)

Uso:
    from radar.adapters.hcaptcha_local import solve_hcaptcha_local
    token = solve_hcaptcha_local()  # bloqueia ~15-25s
    # token = "P1_eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

log = logging.getLogger("radar.hcaptcha_local")

# URL que dispara hCaptcha invisível do SERPRO
HCAPTCHA_PAGE_URL = "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras"

# Concorrência (não abre múltiplos Chromes simultâneos)
_SEM = asyncio.Semaphore(int(os.environ.get("RADAR_HCAPTCHA_LOCAL_CONCURRENCY", "2")))

# Headless ou visível (debug)
_HEADLESS = os.environ.get("RADAR_HCAPTCHA_LOCAL_HEADLESS", "1") == "1"

# Reuso de profile Chrome do user (cookies/histórico aumentam score hCaptcha)
# Path padrão Windows; cliente pode setar RADAR_CHROME_PROFILE_DIR pra override
def _profile_path() -> str | None:
    env = os.environ.get("RADAR_CHROME_PROFILE_DIR")
    if env:
        return env
    # Cria/usa um profile dedicado pra UC (não conflita com Chrome aberto do user)
    import tempfile
    profile = os.path.join(tempfile.gettempdir(), "uc_serpro_profile")
    os.makedirs(profile, exist_ok=True)
    return profile


def _detectar_chrome_major() -> Optional[int]:
    """Lê a versão major do Chrome instalado no Windows pra evitar mismatch com chromedriver."""
    try:
        import subprocess, re
        # Tenta via registro Windows
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Item 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' -ErrorAction SilentlyContinue).VersionInfo.ProductVersion"],
            capture_output=True, text=True, timeout=10,
        )
        version = (result.stdout or "").strip()
        if not version:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-Item 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe' -ErrorAction SilentlyContinue).VersionInfo.ProductVersion"],
                capture_output=True, text=True, timeout=10,
            )
            version = (result.stdout or "").strip()
        m = re.match(r"(\d+)\.", version)
        if m:
            major = int(m.group(1))
            log.info(f"[hcaptcha_local] Chrome detectado v{major}")
            return major
    except Exception as e:
        log.warning(f"falha ao detectar versão Chrome: {e}")
    return None


def _solve_sync(max_attempts: int = 3, headless: bool = True) -> Optional[str]:
    """Função bloqueante — abre Chrome, captura token P1_. Roda em thread."""
    try:
        import undetected_chromedriver as uc
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as e:
        log.error(f"undetected-chromedriver não instalado: {e}")
        return None

    for attempt in range(1, max_attempts + 1):
        driver: Optional[uc.Chrome] = None
        try:
            log.info(f"[hcaptcha_local] tentativa {attempt}/{max_attempts}")
            options = uc.ChromeOptions()
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--incognito")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            if headless:
                options.add_argument("--headless=new")
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins-discovery")
            options.add_argument("--ignore-certificate-errors")
            options.accept_insecure_certs = True

            # Detecta versão major do Chrome instalado pra evitar mismatch com chromedriver
            chrome_major = _detectar_chrome_major()
            driver = uc.Chrome(options=options, version_main=chrome_major) if chrome_major else uc.Chrome(options=options)
            driver.get(HCAPTCHA_PAGE_URL)

            # Espera widget hCaptcha aparecer
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-hcaptcha-widget-id]"))
            )
            log.info("[hcaptcha_local] widget hCaptcha carregado")

            widget_el = driver.find_element(By.CSS_SELECTOR, "[data-hcaptcha-widget-id]")
            widget_id = widget_el.get_attribute("data-hcaptcha-widget-id")
            log.info(f"[hcaptcha_local] widget_id={widget_id}")

            # CRÍTICO: dispara explicitamente hcaptcha.execute() pra iniciar resolução invisível
            driver.execute_script(f"hcaptcha.execute('{widget_id}');")
            log.info("[hcaptcha_local] hcaptcha.execute() disparado, aguardando token...")

            # Polling pelo token resolvido invisivelmente
            t0 = time.monotonic()
            token = WebDriverWait(driver, 25).until(
                lambda d: d.execute_script(
                    f"return hcaptcha.getResponse('{widget_id}');"
                )
            )
            elapsed = time.monotonic() - t0

            if token and len(token) > 50:
                log.info(f"[hcaptcha_local] OK em {elapsed:.1f}s — token len={len(token)}")
                return token
            else:
                log.warning(f"[hcaptcha_local] token vazio/curto: {token!r}")

        except TimeoutException as e:
            log.warning(f"[hcaptcha_local] timeout tentativa {attempt}: {e}")
        except Exception as e:
            log.exception(f"[hcaptcha_local] erro tentativa {attempt}: {e}")
        finally:
            if driver:
                try: driver.quit()
                except Exception: pass

        if attempt < max_attempts:
            time.sleep(2)

    log.error(f"[hcaptcha_local] falhou após {max_attempts} tentativas")
    return None


async def solve_hcaptcha_local(max_attempts: int = 3) -> Optional[str]:
    """Resolve hCaptcha localmente (sitekey SERPRO). Roda em thread pra não bloquear o loop."""
    async with _SEM:
        return await asyncio.to_thread(_solve_sync, max_attempts, _HEADLESS)


async def solve_on_playwright_page(page, sitekey_esperada: str | None = None, timeout_seg: int = 30) -> Optional[str]:
    """Resolve hCaptcha invisível em uma Playwright Page já carregada.

    Use quando o cert .pfx já carregou gov.br SSO ou outra origem onde o widget
    hCaptcha aparece naturalmente. NÃO precisa abrir outro browser — só dispara
    `hcaptcha.execute(widget_id)` no contexto já navegado, evitando "Invalid Host"
    (cada sitekey é bound a domínios específicos pelo dono).

    Retorna o token P1_ ou None.
    """
    try:
        # Espera widget aparecer (até 10s)
        for _ in range(20):
            widget_info = await page.evaluate("""() => {
                if (typeof hcaptcha === 'undefined' || !hcaptcha) return null;
                const div = document.querySelector('[data-hcaptcha-widget-id]');
                if (div) return { wid: div.getAttribute('data-hcaptcha-widget-id'), sitekey: div.getAttribute('data-sitekey') };
                // Fallback: pega via iframe src
                const iframe = document.querySelector('iframe[src*="hcaptcha.com"]');
                if (iframe) {
                    const m = iframe.src.match(/sitekey=([0-9a-f-]+)/);
                    if (m) return { wid: null, sitekey: m[1] };
                }
                return null;
            }""")
            if widget_info and widget_info.get("wid"):
                break
            await page.wait_for_timeout(500)
        else:
            log.warning("solve_on_playwright_page: widget hCaptcha não encontrado na página")
            return None

        widget_id = widget_info["wid"]
        sitekey = widget_info.get("sitekey")
        log.info(f"solve_on_playwright_page: widget_id={widget_id} sitekey={(sitekey or '?')[:12]}...")
        if sitekey_esperada and sitekey != sitekey_esperada:
            log.warning(f"sitekey={sitekey} != esperada={sitekey_esperada}")

        # Dispara execute (resolução invisível)
        await page.evaluate(f"hcaptcha.execute('{widget_id}')")

        # Polling pelo getResponse
        t0 = time.monotonic()
        while (time.monotonic() - t0) < timeout_seg:
            token = await page.evaluate(f"hcaptcha.getResponse('{widget_id}')")
            if token and len(token) > 50:
                elapsed = time.monotonic() - t0
                log.info(f"solve_on_playwright_page OK em {elapsed:.1f}s — token len={len(token)}")
                return token
            await page.wait_for_timeout(500)

        log.warning(f"solve_on_playwright_page timeout após {timeout_seg}s — sem token")
        return None
    except Exception as e:
        log.exception(f"solve_on_playwright_page falhou: {e}")
        return None
