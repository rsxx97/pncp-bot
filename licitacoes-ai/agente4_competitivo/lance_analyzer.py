"""Análise competitiva e sugestão de lance."""
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agente4_competitivo.concorrente_profiler import (
    listar_concorrentes_por_segmento, profiler_concorrente,
)
from agente3_precificador.bdi_simulator import PISO_INEXEQUIBILIDADE_PCT

log = logging.getLogger("lance_analyzer")


def _identificar_segmento(objeto: str) -> str:
    """Identifica segmento do edital pelo objeto."""
    objeto_lower = objeto.lower()
    if any(k in objeto_lower for k in ("limpeza", "conservação", "asseio", "facilities")):
        return "limpeza"
    elif any(k in objeto_lower for k in ("vigilância", "segurança", "vigia")):
        return "vigilancia"
    elif any(k in objeto_lower for k in ("administrativo", "recepção", "portaria", "copeiragem")):
        return "apoio_administrativo"
    elif any(k in objeto_lower for k in ("engenharia", "construção", "reforma", "obra")):
        return "engenharia"
    return "geral"


def analisar_competitividade(
    pncp_id: str,
    objeto: str,
    valor_referencia: float,
    valor_proposta: float,
    prazo_meses: int = 12,
    uf: str = "RJ",
) -> dict:
    """Analisa competitividade e sugere faixa de lance.

    Combina:
    - Piso de inexequibilidade (75% do valor referência)
    - Perfis dos concorrentes esperados
    - Margem mínima viável
    - Valor da nossa planilha (custo real)

    Returns:
        Dict com lance_minimo, lance_sugerido, lance_maximo, etc.
    """
    valor_global_ref = valor_referencia if valor_referencia else 0

    # Piso de inexequibilidade
    piso = valor_global_ref * PISO_INEXEQUIBILIDADE_PCT / 100

    # Margem de segurança acima do piso (5%)
    lance_minimo = max(piso * 1.05, valor_proposta)

    # Concorrentes esperados
    segmento = _identificar_segmento(objeto)
    concorrentes_seg = listar_concorrentes_por_segmento(segmento)

    perfis = []
    concorrentes_nomes = []
    desconto_medio_mercado = 15.0  # default

    for c in concorrentes_seg:
        cnpj = c.get("cnpj", "")
        perfil = profiler_concorrente(cnpj)
        perfis.append(perfil)
        nome = perfil.get("nome_fantasia") or perfil.get("razao_social") or cnpj
        concorrentes_nomes.append(nome)

        if perfil.get("desconto_medio_pct", 0) > 0:
            desconto_medio_mercado = perfil["desconto_medio_pct"]

    # Estratégia de lance
    # Lance sugerido: entre o custo real e o valor de referência
    if valor_global_ref > 0:
        # Desconto alvo: um pouco acima da média do mercado
        desconto_alvo = min(desconto_medio_mercado + 2, 30)  # Max 30%
        lance_sugerido = valor_global_ref * (1 - desconto_alvo / 100)

        # Garantir que está acima do custo real
        if lance_sugerido < valor_proposta:
            lance_sugerido = valor_proposta * 1.02  # 2% acima do custo

        # Garantir que está acima do piso
        if lance_sugerido < piso:
            lance_sugerido = piso * 1.05

        lance_maximo = valor_global_ref * 0.95  # Nunca mais que 95% do referência
    else:
        lance_sugerido = valor_proposta * 1.05
        lance_maximo = valor_proposta * 1.15
        lance_minimo = valor_proposta

    # Margem sobre custo
    margem = ((lance_sugerido - valor_proposta) / valor_proposta * 100) if valor_proposta > 0 else 0

    # Justificativa
    justificativas = []
    if valor_global_ref > 0:
        desconto_real = (1 - lance_sugerido / valor_global_ref) * 100
        justificativas.append(f"Desconto de {desconto_real:.1f}% sobre referência")

    if lance_sugerido > piso:
        justificativas.append(f"Acima do piso de inexequibilidade (R$ {piso:,.2f})")
    else:
        justificativas.append("ALERTA: Próximo ao piso de inexequibilidade!")

    if perfis:
        agressivos = [p for p in perfis if p.get("agressividade") == "alta"]
        if agressivos:
            nomes = [p.get("nome_fantasia", p["cnpj"]) for p in agressivos]
            justificativas.append(f"Concorrentes agressivos: {', '.join(nomes)}")

    justificativas.append(f"Margem sobre custo: {margem:.1f}%")

    return {
        "pncp_id": pncp_id,
        "lance_minimo": round(lance_minimo, 2),
        "lance_sugerido": round(lance_sugerido, 2),
        "lance_maximo": round(lance_maximo, 2),
        "margem_sugerida_pct": round(margem, 2),
        "justificativa": " | ".join(justificativas),
        "concorrentes_esperados": concorrentes_nomes[:5],
        "perfis_concorrentes": perfis,
        "segmento": segmento,
        "piso_inexequibilidade": round(piso, 2),
    }
