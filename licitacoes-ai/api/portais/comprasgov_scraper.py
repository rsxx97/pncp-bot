"""Scraper ComprasGov — extrai dados do pregão em tempo real via Playwright."""
import logging
import json
import re
from typing import Optional

log = logging.getLogger("portal.comprasgov_scraper")


def _formatar_compra_id(uasg: str, numero: str, ano: str, modalidade: int = 5) -> str:
    """Formata ID da compra no padrão ComprasGov: UASG-MODALIDADE-NUMERO-ANO."""
    num = str(numero).zfill(5)
    return f"{uasg}-{modalidade}-{num}-{ano}"


async def scrape_pregao_async(uasg: str, numero: str, ano: str, modalidade: int = 5) -> dict:
    """Scrape assíncrono do pregão no ComprasGov."""
    from playwright.async_api import async_playwright

    compra_id = _formatar_compra_id(uasg, numero, ano, modalidade)
    url = f"https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/acompanhamento-compra?compra={compra_id}"

    result = {
        "portal": "ComprasGov",
        "compra_id": compra_id,
        "url": url,
        "status": None,
        "lances": [],
        "mensagens": [],
        "classificacao": [],
        "propostas": [],
        "vencedor_nome": None,
        "vencedor_valor": None,
        "total_participantes": 0,
        "erro": None,
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            log.info(f"Acessando {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Espera carregar o conteúdo Angular
            await page.wait_for_timeout(5000)

            # Captura todas as requisições XHR que a página fez
            content = await page.content()

            # Tenta extrair dados do DOM
            dados = await page.evaluate("""() => {
                const result = { lances: [], mensagens: [], classificacao: [], status: '', propostas: [] };

                // Status do pregão
                const statusEl = document.querySelector('.situacao-compra, .status-compra, [class*="situacao"]');
                if (statusEl) result.status = statusEl.textContent.trim();

                // Tabela de lances
                const lancesTable = document.querySelectorAll('table');
                lancesTable.forEach(table => {
                    const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim().toLowerCase());
                    if (headers.some(h => h.includes('lance') || h.includes('valor') || h.includes('fornecedor'))) {
                        const rows = table.querySelectorAll('tbody tr');
                        rows.forEach(row => {
                            const cells = Array.from(row.querySelectorAll('td')).map(td => td.textContent.trim());
                            if (cells.length >= 2) {
                                result.lances.push({ cells, raw: row.textContent.trim() });
                            }
                        });
                    }
                });

                // Mensagens do pregoeiro
                const msgElements = document.querySelectorAll('[class*="mensagem"], [class*="chat"], [class*="msg"]');
                msgElements.forEach(el => {
                    const text = el.textContent.trim();
                    if (text.length > 5 && text.length < 1000) {
                        result.mensagens.push(text);
                    }
                });

                // Classificação
                const classElements = document.querySelectorAll('[class*="classificacao"], [class*="ranking"], [class*="resultado"]');
                classElements.forEach(el => {
                    const text = el.textContent.trim();
                    if (text.length > 5) {
                        result.classificacao.push(text);
                    }
                });

                // Pega todo texto da página para parsing posterior
                result.fullText = document.body.innerText.substring(0, 50000);

                return result;
            }""")

            # Parse do texto completo para extrair dados estruturados
            full_text = dados.get("fullText", "")

            # Extrai status
            status_match = re.search(r'(?:Situação|Status)[:\s]*([^\n]+)', full_text, re.IGNORECASE)
            if status_match:
                result["status"] = status_match.group(1).strip()

            # Extrai lances do texto
            lance_pattern = re.compile(
                r'(?:(\d+)[°ºª]?\s*)?'  # posição
                r'(?:(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s*-?\s*)?'  # CNPJ
                r'([A-ZÀ-Ú][A-ZÀ-Ú\s&.,\'-]{3,50}?)\s*'  # empresa
                r'R?\$?\s*([\d.,]+(?:\.\d{2}))',  # valor
                re.IGNORECASE
            )
            for m in lance_pattern.finditer(full_text):
                pos, cnpj, empresa, valor = m.groups()
                try:
                    valor_float = float(valor.replace('.', '').replace(',', '.'))
                    result["lances"].append({
                        "posicao": int(pos) if pos else None,
                        "cnpj": cnpj,
                        "empresa": empresa.strip(),
                        "valor": valor_float,
                    })
                except ValueError:
                    pass

            # Extrai mensagens do pregoeiro
            msg_pattern = re.compile(
                r'(?:Pregoeiro|Sistema|PREGOEIRO)[:\s]*(.+?)(?:\n|$)',
                re.IGNORECASE
            )
            for m in msg_pattern.finditer(full_text):
                msg = m.group(1).strip()
                if len(msg) > 5:
                    result["mensagens"].append({
                        "remetente": "pregoeiro",
                        "mensagem": msg[:500],
                        "horario": None,
                    })

            # Conta participantes e identifica vencedor
            if result["lances"]:
                empresas_unicas = set(l["empresa"] for l in result["lances"] if l.get("empresa"))
                result["total_participantes"] = len(empresas_unicas)

                # Menor lance = provável vencedor
                sorted_lances = sorted([l for l in result["lances"] if l.get("valor")], key=lambda x: x["valor"])
                if sorted_lances:
                    result["vencedor_nome"] = sorted_lances[0]["empresa"]
                    result["vencedor_valor"] = sorted_lances[0]["valor"]

                    # Monta classificação
                    for i, l in enumerate(sorted_lances):
                        result["classificacao"].append({
                            "posicao": i + 1,
                            "empresa": l["empresa"],
                            "cnpj": l.get("cnpj"),
                            "valor_lance_final": l["valor"],
                            "habilitado": True,
                        })

            await browser.close()

    except ImportError:
        result["erro"] = "Playwright não instalado. Execute: pip install playwright && python -m playwright install chromium"
    except Exception as e:
        result["erro"] = f"Erro no scraping ComprasGov: {str(e)}"
        log.error(f"Scraping falhou: {e}", exc_info=True)

    return result


def scrape_pregao(uasg: str, numero: str, ano: str, modalidade: int = 5) -> dict:
    """Versão síncrona do scraper."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Se já estamos em um loop async (FastAPI), cria um novo
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, scrape_pregao_async(uasg, numero, ano, modalidade))
                return future.result(timeout=60)
        else:
            return asyncio.run(scrape_pregao_async(uasg, numero, ano, modalidade))
    except Exception as e:
        return {
            "portal": "ComprasGov",
            "erro": f"Erro executando scraper: {str(e)}",
            "lances": [], "mensagens": [], "classificacao": [],
        }


def extrair_numero_pregao(pncp_id: str) -> tuple:
    """Extrai número e ano do pregão a partir do pncp_id."""
    parts = pncp_id.split("-")
    if len(parts) >= 3:
        return parts[2], parts[1]  # seq, ano
    return None, None
