"""Funções utilitárias gerais."""
import json
import re
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import KEYWORDS_INTERESSE, KEYWORDS_EXCLUSAO


def formatar_valor(valor: float | None) -> str:
    """Formata valor em Reais brasileiro."""
    if valor is None:
        return "Não informado"
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "Não informado"


def formatar_data(data_str: str | None) -> str:
    """Formata data ISO para dd/mm/aaaa HH:MM."""
    if not data_str:
        return "Não informada"
    try:
        dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return data_str


def gerar_pncp_id(cnpj: str, ano: str | int, seq: str | int) -> str:
    """Gera ID único no formato cnpj-ano-seq."""
    return f"{cnpj}-{ano}-{seq}"


def gerar_link_pncp(cnpj: str, ano: str | int, seq: str | int) -> str:
    """Gera link para o edital no portal PNCP."""
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"


def contem_palavra_chave(texto: str, palavras: list[str] | None = None) -> bool:
    """Verifica se o texto contém alguma das palavras-chave."""
    if not texto:
        return False
    if palavras is None:
        palavras = KEYWORDS_INTERESSE
    texto_lower = texto.lower().replace("-", " ")
    return any(p.lower().replace("-", " ") in texto_lower for p in palavras)


def contem_exclusao(texto: str, palavras: list[str] | None = None) -> bool:
    """Verifica se o texto contém palavras de exclusão."""
    if not texto:
        return False
    if palavras is None:
        palavras = KEYWORDS_EXCLUSAO
    texto_lower = texto.lower().replace("-", " ")
    return any(p.lower().replace("-", " ") in texto_lower for p in palavras)


def derivar_esfera(cnpj_orgao: str) -> str:
    """Deriva esfera administrativa a partir do CNPJ do órgão.

    Heurística baseada na estrutura de CNPJs:
    - Órgãos federais geralmente começam com 00 ou 03
    - Prefeituras e câmaras municipais variam
    - Sem regra exata, mas ajuda na triagem
    """
    if not cnpj_orgao:
        return "desconhecida"
    # CNPJs de órgãos federais conhecidos
    prefixos_federais = ("00394", "00402", "00394", "26994", "00083", "33683")
    if cnpj_orgao[:5] in prefixos_federais:
        return "federal"
    # Heurística: se começa com 00, geralmente é federal
    if cnpj_orgao.startswith("00"):
        return "federal"
    return "estadual_municipal"


def truncar_texto(texto: str, max_chars: int = 300) -> str:
    """Trunca texto com reticências."""
    if not texto or len(texto) <= max_chars:
        return texto or ""
    return texto[:max_chars] + "..."


def limpar_texto_pdf(texto: str) -> str:
    """Limpa texto extraído de PDF (remove quebras excessivas, espaços, etc)."""
    # Remove múltiplas quebras de linha
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    # Remove espaços múltiplos
    texto = re.sub(r" {2,}", " ", texto)
    # Remove linhas com apenas espaços
    texto = re.sub(r"\n\s+\n", "\n\n", texto)
    return texto.strip()
