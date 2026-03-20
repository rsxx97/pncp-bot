"""Parsing estruturado de editais via LLM."""
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.llm_client import ask_claude_json
from agente2_analista.prompts import SYSTEM_EDITAL_PARSER, build_user_prompt_analise

log = logging.getLogger("edital_parser")


def extrair_dados_estruturados(texto_edital: str, pncp_id: str = None) -> dict:
    """Envia texto do edital ao Claude e retorna dados estruturados.

    Args:
        texto_edital: Texto extraído do PDF
        pncp_id: ID para tracking

    Returns:
        Dict com dados estruturados do edital
    """
    log.info(f"Analisando edital via LLM ({len(texto_edital)} chars)...")

    result = ask_claude_json(
        system=SYSTEM_EDITAL_PARSER,
        user=build_user_prompt_analise(texto_edital),
        max_tokens=4096,
        agente="analista_parser",
        pncp_id=pncp_id,
    )

    # Validações básicas
    if not result.get("objeto_detalhado"):
        log.warning("LLM não extraiu objeto_detalhado")

    postos = result.get("postos_trabalho", [])
    log.info(f"Extraídos: {len(postos)} postos, parecer implícito dos dados")

    return result
