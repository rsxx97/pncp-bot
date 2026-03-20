"""Download e extração de texto/tabelas de PDFs de editais."""
import logging
import re
from pathlib import Path

import httpx
import pdfplumber

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import EDITAIS_DIR
from shared.utils import limpar_texto_pdf

log = logging.getLogger("pdf_extractor")

# Seções importantes para extrair quando o PDF é muito grande
SECOES_RELEVANTES = [
    r"(?:DO\s+)?OBJETO",
    r"OBJETO\s+DA\s+CONTRATA",
    r"HABILITA[ÇC][ÃA]O",
    r"DOCUMENTOS?\s+DE\s+HABILITA",
    r"PROPOSTA",
    r"PROPOSTA\s+DE\s+PRE[ÇC]O",
    r"QUALIFICA[ÇC][ÃA]O\s+T[ÉE]CNICA",
    r"QUALIFICA[ÇC][ÃA]O\s+ECON[ÔO]MICA",
    r"PLANILHA\s+DE\s+CUSTOS",
    r"ENCARGOS",
    r"POSTOS?\s+DE\s+TRABALHO",
    r"DESCRI[ÇC][ÃA]O\s+DOS\s+SERVI",
    r"JORNADA",
    r"CONVEN[ÇC][ÃA]O\s+COLETIVA",
]

MAX_CHARS = 80_000  # Limite de contexto para o LLM


def download_pdf(url: str, filename: str = None) -> Path:
    """Baixa PDF e salva em data/editais/. Retorna o path."""
    EDITAIS_DIR.mkdir(parents=True, exist_ok=True)

    if not filename:
        filename = url.split("/")[-1]
        if not filename.endswith(".pdf"):
            filename += ".pdf"

    save_path = EDITAIS_DIR / filename

    if save_path.exists():
        log.info(f"PDF já existe: {save_path}")
        return save_path

    log.info(f"Baixando PDF: {url}")
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        save_path.write_bytes(resp.content)

    log.info(f"PDF salvo: {save_path} ({save_path.stat().st_size / 1024:.0f} KB)")
    return save_path


def extract_text(pdf_path: Path | str) -> str:
    """Extrai texto completo do PDF."""
    pdf_path = Path(pdf_path)
    text_parts = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        log.info(f"PDF: {total_pages} páginas")

        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    full_text = "\n\n".join(text_parts)
    return limpar_texto_pdf(full_text)


def extract_tables(pdf_path: Path | str) -> list[list[list[str]]]:
    """Extrai tabelas do PDF."""
    pdf_path = Path(pdf_path)
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)

    return all_tables


def extract_smart(pdf_path: Path | str) -> dict:
    """Extração inteligente: texto completo se pequeno, seções relevantes se grande.

    Returns:
        {"text": str, "tables": list, "pages": int, "truncated": bool}
    """
    pdf_path = Path(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        log.info(f"PDF: {total_pages} páginas")

        # Se pequeno (<= 50 páginas), extrai tudo
        if total_pages <= 50:
            text_parts = []
            all_tables = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)

            full_text = limpar_texto_pdf("\n\n".join(text_parts))
            truncated = len(full_text) > MAX_CHARS
            if truncated:
                full_text = full_text[:MAX_CHARS] + "\n\n[... TEXTO TRUNCADO ...]"

            return {
                "text": full_text,
                "tables": all_tables,
                "pages": total_pages,
                "truncated": truncated,
            }

        # Se grande (> 50 páginas), extrai seções relevantes
        log.info("PDF grande — extraindo seções relevantes")

        # Sempre extrai primeiras 5 páginas (capa, preâmbulo)
        text_parts = []
        all_tables = []

        for i, page in enumerate(pdf.pages[:5]):
            t = page.extract_text()
            if t:
                text_parts.append(f"--- Página {i+1} ---\n{t}")
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)

        # Extrai o restante procurando seções relevantes
        secao_pattern = re.compile(
            "|".join(SECOES_RELEVANTES), re.IGNORECASE
        )

        for i, page in enumerate(pdf.pages[5:], start=6):
            t = page.extract_text()
            if not t:
                continue

            if secao_pattern.search(t):
                text_parts.append(f"--- Página {i} ---\n{t}")
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)

                # Também pega as 2 próximas páginas (continuação da seção)
                for j in range(1, 3):
                    if i - 1 + j < total_pages:
                        next_page = pdf.pages[i - 1 + j]
                        nt = next_page.extract_text()
                        if nt:
                            text_parts.append(f"--- Página {i+j} ---\n{nt}")

        full_text = limpar_texto_pdf("\n\n".join(text_parts))
        truncated = len(full_text) > MAX_CHARS
        if truncated:
            full_text = full_text[:MAX_CHARS] + "\n\n[... TEXTO TRUNCADO ...]"

        return {
            "text": full_text,
            "tables": all_tables,
            "pages": total_pages,
            "truncated": truncated,
        }


def extract_all(pdf_path: Path | str) -> dict:
    """Alias para extract_smart."""
    return extract_smart(pdf_path)
