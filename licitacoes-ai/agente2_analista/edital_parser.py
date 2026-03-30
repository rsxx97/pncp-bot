"""Parsing estruturado de editais via LLM — envia edital + TR juntos."""
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.llm_client import ask_claude_json
from agente2_analista.prompts import SYSTEM_EDITAL_PARSER, build_user_prompt_analise

log = logging.getLogger("edital_parser")


def extrair_dados_estruturados(texto_edital: str, pncp_id: str = None, texto_tr: str = None) -> dict:
    """Envia texto do edital + TR ao LLM e retorna dados estruturados.

    Args:
        texto_edital: Texto extraído do PDF do edital
        pncp_id: ID para tracking
        texto_tr: Texto extraído do TR (opcional mas recomendado)

    Returns:
        Dict com dados estruturados (postos, CCT, habilitação, etc.)
    """
    log.info(f"Analisando edital via LLM ({len(texto_edital)} chars edital"
             f"{f', {len(texto_tr)} chars TR' if texto_tr else ''})...")

    user_prompt = build_user_prompt_analise(texto_edital, texto_tr)

    result = ask_claude_json(
        system=SYSTEM_EDITAL_PARSER,
        user=user_prompt,
        max_tokens=4096,
        agente="analista_parser",
        pncp_id=pncp_id,
    )

    # Validações e correções
    postos = result.get("postos_trabalho", [])

    # Corrigir quantidade None
    for p in postos:
        if p.get("quantidade") is None:
            p["quantidade"] = 1
        # Garantir que quantidade é int
        try:
            p["quantidade"] = int(p["quantidade"])
        except (ValueError, TypeError):
            p["quantidade"] = 1

        # Normalizar jornada
        jornada = p.get("jornada", "44h")
        if not jornada:
            jornada = "44h"
        # Telefonista sempre 30h
        funcao = (p.get("funcao") or "").lower()
        if "telefonist" in funcao and "44" in str(jornada):
            p["jornada"] = "30h"
            log.info(f"Corrigido: {p['funcao']} jornada 44h -> 30h (CLT art 227)")

    # Filtrar postos que são materiais (proteção contra erro do LLM)
    materiais_keywords = ["litro", "kg", "pacote", "galão", "rolo", "par", "caixa", "unidade"]
    postos_limpos = []
    for p in postos:
        desc = (p.get("descricao") or p.get("funcao") or "").lower()
        is_material = any(k in desc for k in materiais_keywords) and not any(
            c in desc for c in ["servente", "encarregado", "vigia", "porteiro", "copeiro",
                                "recepcionista", "secretar", "motorista", "telefonist", "garçom"]
        )
        if is_material:
            log.warning(f"Removido posto que parece material: {p.get('funcao')}")
            # Move para materiais
            if "materiais_insumos" not in result:
                result["materiais_insumos"] = []
            result["materiais_insumos"].append({
                "item": p.get("funcao", ""),
                "unidade": "un",
                "qtd_mensal": p.get("quantidade", 1),
                "valor_estimado": None,
            })
        else:
            postos_limpos.append(p)

    result["postos_trabalho"] = postos_limpos

    log.info(f"Resultado: {len(postos_limpos)} postos, "
             f"parecer={result.get('parecer', 'N/A')}, "
             f"CCT={result.get('cct', {}).get('sindicato_patronal', 'N/A')}")

    return result
