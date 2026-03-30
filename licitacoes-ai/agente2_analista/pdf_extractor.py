"""Download e extração de texto/tabelas de PDFs de editais."""
import logging
import os
import re
import zipfile
import tempfile
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

MAX_CHARS = 120_000  # Ampliado para capturar TRs longos sem truncar


def download_pdf(url: str, filename: str = None) -> Path:
    """Baixa arquivo do PNCP e salva em data/editais/.

    Se o arquivo for um ZIP, extrai o primeiro PDF encontrado.
    Retorna o path do PDF.
    """
    EDITAIS_DIR.mkdir(parents=True, exist_ok=True)

    if not filename:
        filename = url.split("/")[-1]
        if not filename.endswith(".pdf"):
            filename += ".pdf"

    save_path = EDITAIS_DIR / filename

    if save_path.exists():
        log.info(f"PDF já existe: {save_path}")
        return save_path

    log.info(f"Baixando: {url}")
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        content = resp.content

    # Detectar tipo de arquivo pelos magic bytes
    if content[:2] == b'PK':
        # É um ZIP — extrair PDFs
        log.info("Arquivo é ZIP, extraindo PDFs...")
        return _extrair_pdf_do_zip(content, save_path)
    elif content[:5] == b'%PDF-':
        # É PDF direto
        save_path.write_bytes(content)
        log.info(f"PDF salvo: {save_path} ({save_path.stat().st_size / 1024:.0f} KB)")
        return save_path
    else:
        # Tenta salvar como PDF mesmo assim (pode ser PDF sem header padrão)
        save_path.write_bytes(content)
        log.warning(f"Tipo desconhecido, salvo como: {save_path}")
        return save_path


def _extrair_pdf_do_zip(zip_bytes: bytes, save_path: Path, depth: int = 0) -> Path:
    """Extrai TODOS os documentos de um ZIP (recursivo para ZIP dentro de ZIP)."""
    import io
    if depth > 3:
        raise ValueError("ZIP aninhado demais (>3 niveis)")

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    pncp_id = save_path.stem.replace('.pdf', '')
    out_dir = save_path.parent

    # Primeiro, descompactar ZIPs internos recursivamente
    inner_zips = [n for n in zf.namelist() if n.lower().endswith('.zip')]
    for iz in inner_zips:
        log.info(f"ZIP interno encontrado: {iz}, descompactando...")
        inner_bytes = zf.read(iz)
        _extrair_pdf_do_zip(inner_bytes, save_path, depth + 1)

    # Extrair todos os PDFs, XLSX, ODS, DOC
    doc_exts = ('.pdf', '.xlsx', '.xls', '.ods', '.doc', '.docx')
    all_docs = [n for n in zf.namelist() if any(n.lower().endswith(e) for e in doc_exts)]

    edital_pdf = None
    tr_pdf = None
    for name in all_docs:
        nl = name.lower()
        base = os.path.basename(name).replace(' ', '_')
        safe_name = f"{pncp_id}_{base}"
        out_path = out_dir / safe_name

        # Extrai o arquivo
        content = zf.read(name)
        out_path.write_bytes(content)
        log.info(f"Extraido: {out_path.name} ({len(content) // 1024} KB)")

        # Identifica edital e TR
        if nl.endswith('.pdf'):
            if 'edital' in nl and not edital_pdf:
                edital_pdf = out_path
            elif ('termo' in nl and 'referencia' in nl) or '-tr' in nl or '_tr' in nl or 'anexo-i-tr' in nl or 'anexo_i_tr' in nl:
                tr_pdf = out_path

    # Salva o edital principal no path esperado (só se ainda não existe do ZIP interno)
    if edital_pdf and edital_pdf != save_path:
        import shutil
        shutil.copy2(str(edital_pdf), str(save_path))
        log.info(f"Edital principal: {save_path.name}")
    elif not edital_pdf and all_docs and not (save_path.exists() and save_path.stat().st_size > 100_000):
        # Pega o maior PDF como edital, mas só se não já tem um edital grande do ZIP interno
        pdfs = [out_dir / f"{pncp_id}_{os.path.basename(n).replace(' ', '_')}" for n in all_docs if n.lower().endswith('.pdf')]
        pdfs = [p for p in pdfs if p.exists()]
        if pdfs:
            biggest = max(pdfs, key=lambda f: f.stat().st_size)
            import shutil
            shutil.copy2(str(biggest), str(save_path))

    # Copia TR para o path padrao _TR.pdf
    if tr_pdf:
        tr_std = out_dir / save_path.name.replace('.pdf', '_TR.pdf')
        if tr_pdf != tr_std:
            import shutil
            shutil.copy2(str(tr_pdf), str(tr_std))
            log.info(f"TR copiado para: {tr_std.name}")

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
