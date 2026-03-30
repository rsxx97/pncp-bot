"""Busca documentos de editais em sites de orgaos quando PNCP nao tem TR."""
import logging
import re
from pathlib import Path
from urllib.parse import urljoin

import httpx

log = logging.getLogger("doc_scraper")


def buscar_docs_site_orgao(url_orgao: str, numero_pregao: str = None) -> list[dict]:
    """Busca todos os documentos de licitacao no site do orgao.

    Args:
        url_orgao: URL da pagina de licitacoes do orgao
        numero_pregao: Numero do pregao para filtrar (ex: "003/2026")

    Returns:
        Lista de dicts com {titulo, url, tipo}
    """
    docs = []
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url_orgao)
            if resp.status_code != 200:
                log.warning(f"Site {url_orgao} retornou {resp.status_code}")
                return []

            html = resp.text
            base_url = str(resp.url)

            # Busca links para documentos
            # Padrao: href="...pdf" ou href="...xlsx" etc
            link_pattern = re.compile(
                r'href=["\']([^"\']*\.(?:pdf|xlsx|xls|doc|docx|zip|rar|odt))["\']',
                re.IGNORECASE
            )

            for match in link_pattern.finditer(html):
                href = match.group(1)
                full_url = urljoin(base_url, href)

                # Extrai titulo do nome do arquivo
                filename = href.split("/")[-1]
                filename = filename.replace("%20", " ").replace("+", " ")

                # Se numero_pregao fornecido, filtra
                if numero_pregao:
                    # Normaliza para comparacao
                    num_clean = numero_pregao.replace("/", "").replace("-", "")
                    href_clean = href.replace("/", "").replace("-", "").replace("%20", "")
                    if num_clean not in href_clean and numero_pregao not in href:
                        continue

                # Classifica tipo
                tipo = classificar_documento(filename)

                docs.append({
                    "titulo": filename,
                    "url": full_url,
                    "tipo": tipo,
                })

            # Se nao achou com filtro de pregao, busca paginas internas
            if not docs and numero_pregao:
                # Busca links para paginas internas que contenham o numero
                page_pattern = re.compile(
                    r'href=["\']([^"\']*(?:node|licitacao|pregao|edital)[^"\']*)["\']',
                    re.IGNORECASE
                )
                for match in page_pattern.finditer(html):
                    page_url = urljoin(base_url, match.group(1))
                    try:
                        resp2 = client.get(page_url)
                        if resp2.status_code == 200 and numero_pregao.replace("/", "") in resp2.text:
                            # Busca docs nessa pagina
                            for match2 in link_pattern.finditer(resp2.text):
                                href2 = match2.group(1)
                                full_url2 = urljoin(str(resp2.url), href2)
                                filename2 = href2.split("/")[-1].replace("%20", " ")
                                docs.append({
                                    "titulo": filename2,
                                    "url": full_url2,
                                    "tipo": classificar_documento(filename2),
                                })
                            if docs:
                                break
                    except Exception:
                        continue

    except Exception as e:
        log.error(f"Erro ao buscar docs em {url_orgao}: {e}")

    log.info(f"Encontrados {len(docs)} documentos em {url_orgao}")
    return docs


def classificar_documento(filename: str) -> str:
    """Classifica tipo de documento pelo nome do arquivo."""
    f = filename.lower()
    if "termo" in f or "referencia" in f or " tr " in f or "_tr_" in f or f.startswith("tr "):
        return "TR"
    if "edital" in f:
        return "Edital"
    if "planilha" in f or "mao de obra" in f or "mdo" in f or "custos" in f:
        return "Planilha"
    if "minuta" in f or "contrat" in f:
        return "Minuta"
    if "anexo" in f:
        return "Anexo"
    if "ata" in f:
        return "Ata"
    return "Documento"


def baixar_docs_orgao(docs: list[dict], pncp_id: str, editais_dir: Path) -> list[Path]:
    """Baixa todos os documentos encontrados.

    Returns:
        Lista de paths dos arquivos baixados
    """
    downloaded = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for i, doc in enumerate(docs):
            try:
                resp = client.get(doc["url"])
                if resp.status_code != 200:
                    log.warning(f"Erro {resp.status_code} ao baixar {doc['titulo']}")
                    continue

                # Nome seguro
                safe_name = re.sub(r'[^\w\s\-.]', '_', doc["titulo"])
                out_path = editais_dir / f"{pncp_id}_{safe_name}"
                out_path.write_bytes(resp.content)
                downloaded.append(out_path)
                log.info(f"Baixado: {safe_name} ({len(resp.content) // 1024}KB)")

            except Exception as e:
                log.warning(f"Erro ao baixar {doc['titulo']}: {e}")

    return downloaded


# Sites conhecidos de orgaos
SITES_ORGAOS = {
    "nuclep": "https://www.nuclep.gov.br/licitacoes",
    "comprasnet": "https://www.gov.br/compras/pt-br",
    "comprasrj": "https://www.compras.rj.gov.br",
    "licitacoes-e": "https://licitacoes-e2.bb.com.br",
}
