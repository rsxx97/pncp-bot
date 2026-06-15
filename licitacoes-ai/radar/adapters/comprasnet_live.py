"""Captura ao vivo de lances/mensagens/fase do ComprasNet via Playwright.

Visita a página pública de acompanhamento da compra:
  https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/acompanhamento-compra?compra=UASG-MOD-NUM-ANO

Browser é singleton para amortizar custo entre ticks do worker. O contexto
(page) é criado e descartado por chamada.

Se playwright não está instalado/inicializável, levanta ImportError —
ComprasnetAdapter trata como degradação graciosa (segue só com API leve).
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

log = logging.getLogger("radar.comprasnet.live")

_BROWSER: Any = None
_PLAYWRIGHT: Any = None
_LOCK = asyncio.Lock()

URL_TPL = (
    "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/"
    "acompanhamento-compra?compra={compra}"
)

CNPJ_RE = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
VALOR_RE = re.compile(r"R?\$?\s*([\d.]+,\d{2})")


def _parse_valor(s: str) -> float | None:
    m = VALOR_RE.search(s or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


async def _obter_browser():
    global _BROWSER, _PLAYWRIGHT
    async with _LOCK:
        if _BROWSER is not None:
            try:
                if _BROWSER.is_connected():
                    return _BROWSER
            except Exception:
                pass
        from playwright.async_api import async_playwright
        _PLAYWRIGHT = await async_playwright().start()
        _BROWSER = await _PLAYWRIGHT.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        log.info("browser Playwright iniciado (singleton)")
        return _BROWSER


async def encerrar_browser():
    """Chama no shutdown do FastAPI."""
    global _BROWSER, _PLAYWRIGHT
    if _BROWSER is not None:
        try:
            await _BROWSER.close()
        except Exception:
            pass
        _BROWSER = None
    if _PLAYWRIGHT is not None:
        try:
            await _PLAYWRIGHT.stop()
        except Exception:
            pass
        _PLAYWRIGHT = None


async def extrair_live(compra_id: str, timeout_seg: int = 25) -> dict:
    """Extrai snapshot ao vivo. Retorna dict possivelmente parcial.

    Shape:
      {
        "fase": str | None,
        "lances": [{"posicao": int, "empresa": str, "cnpj": str|None, "valor": float}],
        "mensagens": [{"remetente": str, "mensagem": str, "horario": str|None}],
        "melhor_lance": float | None,
        "melhor_lance_cnpj": str | None,
        "raw_text_size": int,
      }
    """
    url = URL_TPL.format(compra=compra_id)
    browser = await _obter_browser()
    ctx = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 900},
    )
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seg * 1000)
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(2500)

        dados = await page.evaluate(_JS_EXTRACT)
        full_text = dados.get("fullText", "") or ""

        lances = _parsear_lances(dados.get("tabelas") or [], full_text)
        mensagens = _parsear_mensagens(full_text)
        fase = _detectar_fase(full_text)

        melhor_lance = None
        melhor_cnpj = None
        if lances:
            lances_ord = sorted(
                [l for l in lances if l.get("valor")],
                key=lambda x: x["valor"],
            )
            if lances_ord:
                melhor_lance = lances_ord[0]["valor"]
                melhor_cnpj = lances_ord[0].get("cnpj")

        return {
            "fase": fase,
            "lances": lances,
            "mensagens": mensagens,
            "melhor_lance": melhor_lance,
            "melhor_lance_cnpj": melhor_cnpj,
            "raw_text_size": len(full_text),
        }
    finally:
        await ctx.close()


_JS_EXTRACT = """
() => {
  const out = { fullText: '', tabelas: [] };
  out.fullText = (document.body && document.body.innerText) ? document.body.innerText.substring(0, 80000) : '';
  const tables = document.querySelectorAll('table');
  tables.forEach(t => {
    const headers = Array.from(t.querySelectorAll('th, thead td')).map(th => (th.textContent || '').trim().toLowerCase());
    const rows = Array.from(t.querySelectorAll('tbody tr, tr')).map(tr =>
      Array.from(tr.querySelectorAll('td')).map(td => (td.textContent || '').trim())
    ).filter(r => r.length > 1);
    if (rows.length) out.tabelas.push({ headers, rows });
  });
  return out;
}
"""


def _parsear_lances(tabelas: list[dict], full_text: str) -> list[dict]:
    """Procura tabela cujos headers tenham 'lance'/'valor'/'fornecedor'."""
    lances: list[dict] = []
    seen = set()
    for t in tabelas:
        headers = " ".join(t.get("headers") or [])
        if not any(k in headers for k in ("lance", "valor", "fornecedor", "proposta")):
            continue
        for row in t.get("rows") or []:
            joined = " ".join(row)
            valor = _parse_valor(joined)
            if valor is None:
                continue
            cnpj_m = CNPJ_RE.search(joined)
            cnpj = cnpj_m.group(0) if cnpj_m else None
            empresa = None
            for cell in row:
                if len(cell) > 4 and not CNPJ_RE.fullmatch(cell.strip()) and not VALOR_RE.fullmatch(cell.strip()):
                    if not re.fullmatch(r"[\d\s.,/-]+", cell):
                        empresa = cell.strip()
                        break
            key = (empresa, cnpj, valor)
            if key in seen:
                continue
            seen.add(key)
            lances.append({
                "posicao": len(lances) + 1,
                "empresa": empresa,
                "cnpj": cnpj,
                "valor": valor,
            })
    return lances


def _parsear_mensagens(full_text: str) -> list[dict]:
    pat = re.compile(
        r"(Pregoeiro|Sistema|Fornecedor)[:\s]+(.+?)(?=\n(?:Pregoeiro|Sistema|Fornecedor)[:\s]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    msgs = []
    for m in pat.finditer(full_text):
        remetente = m.group(1).strip().lower()
        texto = m.group(2).strip()[:500]
        if len(texto) > 4:
            msgs.append({"remetente": remetente, "mensagem": texto, "horario": None})
        if len(msgs) >= 50:
            break
    return msgs


def _detectar_fase(full_text: str) -> str | None:
    t = full_text.lower()
    pares = [
        ("homologa", "homologacao"),
        ("adjudica", "adjudicacao"),
        ("habilita", "habilitacao"),
        ("negocia", "negociacao"),
        ("lance", "lances"),
        ("proposta", "propostas"),
    ]
    for needle, fase in pares:
        if needle in t:
            return fase
    return None
