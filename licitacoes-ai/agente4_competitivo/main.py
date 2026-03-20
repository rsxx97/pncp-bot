"""Agente 4 — Competitivo: análise de concorrência e sugestão de lance."""
import json
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_DIR
from shared.database import (
    get_edital, get_editais_pendentes, atualizar_status_edital,
    adicionar_comentario, init_db,
)
from shared.llm_client import ask_claude_json
from agente4_competitivo.concorrente_profiler import sincronizar_concorrentes
from agente4_competitivo.lance_analyzer import analisar_competitividade
from agente4_competitivo.prompts import (
    SYSTEM_ANALISE_COMPETITIVA, PROMPT_ANALISE_COMPETITIVA,
)

log = logging.getLogger("agente4_competitivo")


def _formatar_concorrentes(perfis: list[dict]) -> str:
    """Formata perfis de concorrentes para o prompt."""
    if not perfis:
        return "Nenhum concorrente identificado."

    linhas = []
    for p in perfis[:5]:
        nome = p.get("nome_fantasia") or p.get("razao_social") or p.get("cnpj")
        historico = p.get("historico", {})
        linhas.append(
            f"- {nome}: {historico.get('total_participacoes', 0)} participações, "
            f"taxa vitória {historico.get('taxa_vitoria_pct', 0):.1f}%, "
            f"agressividade {p.get('agressividade', '?')}"
        )
    return "\n".join(linhas)


def _formatar_cenarios(cenarios: list[dict]) -> str:
    """Formata cenários BDI para o prompt."""
    if not cenarios:
        return "Não disponível."

    linhas = []
    for c in cenarios:
        linhas.append(
            f"- {c.get('cenario', '?').title()}: BDI {c.get('bdi_pct', 0):.2f}%, "
            f"R$ {c.get('valor_global', 0):,.2f} "
            f"(desconto {c.get('desconto_sobre_referencia_pct', 0):.1f}%)"
        )
    return "\n".join(linhas)


def analisar_edital_competitivo(pncp_id: str) -> dict | None:
    """Pipeline de análise competitiva para um edital precificado.

    Fluxo:
    1. Carrega edital do banco (já precificado)
    2. Analisa competitividade (rule-based)
    3. Enriquece com LLM para estratégia
    4. Atualiza banco
    """
    edital = get_edital(pncp_id)
    if not edital:
        log.error(f"Edital {pncp_id} não encontrado.")
        return None

    valor_proposta = edital.get("valor_proposta", 0)
    valor_referencia = edital.get("valor_estimado", 0)
    bdi_pct = edital.get("bdi_percentual", 0)
    prazo_meses = 12

    analise_json = edital.get("analise_json")
    if analise_json:
        analise = json.loads(analise_json) if isinstance(analise_json, str) else analise_json
        prazo_meses = analise.get("prazo_contrato_meses", 12) or 12
    else:
        analise = {}

    # 1. Análise rule-based
    resultado_comp = analisar_competitividade(
        pncp_id=pncp_id,
        objeto=edital.get("objeto", ""),
        valor_referencia=valor_referencia,
        valor_proposta=valor_proposta,
        prazo_meses=prazo_meses,
        uf=edital.get("uf", "RJ"),
    )

    # 2. Enriquecimento via LLM
    try:
        concorrentes_texto = _formatar_concorrentes(resultado_comp.get("perfis_concorrentes", []))

        # Cenários BDI do edital (se disponível)
        cenarios_texto = "Não disponível."

        prompt = PROMPT_ANALISE_COMPETITIVA.format(
            objeto=edital.get("objeto", ""),
            valor_referencia=f"{valor_referencia:,.2f}",
            uf=edital.get("uf", "RJ"),
            adjudicacao=analise.get("adjudicacao", "menor preço"),
            prazo_meses=prazo_meses,
            valor_proposta=f"{valor_proposta:,.2f}",
            bdi_pct=f"{bdi_pct:.2f}",
            margem_pct=f"{resultado_comp.get('margem_sugerida_pct', 0):.1f}",
            piso_inexequibilidade=f"{resultado_comp.get('piso_inexequibilidade', 0):,.2f}",
            concorrentes_texto=concorrentes_texto,
            cenarios_texto=cenarios_texto,
        )

        llm_result = ask_claude_json(
            system=SYSTEM_ANALISE_COMPETITIVA,
            user=prompt,
            max_tokens=2000,
            agente="competitivo",
            pncp_id=pncp_id,
        )

        # Merge LLM com rule-based
        if llm_result.get("lance_recomendado"):
            resultado_comp["lance_llm"] = llm_result["lance_recomendado"]
        resultado_comp["estrategia"] = llm_result.get("estrategia", "moderada")
        resultado_comp["riscos"] = llm_result.get("riscos", [])
        resultado_comp["oportunidades"] = llm_result.get("oportunidades", [])
        resultado_comp["dicas_negociacao"] = llm_result.get("dicas_negociacao", [])
        if llm_result.get("justificativa"):
            resultado_comp["justificativa_llm"] = llm_result["justificativa"]

    except Exception as e:
        log.warning(f"LLM indisponível para análise competitiva: {e}. Usando apenas rule-based.")

    # 3. Atualizar banco
    analise_comp_json = json.dumps(resultado_comp, ensure_ascii=False, default=str)

    atualizar_status_edital(
        pncp_id,
        status="competitivo_pronto",
        analise_competitiva_json=analise_comp_json,
        lance_sugerido_min=resultado_comp["lance_minimo"],
        lance_sugerido_max=resultado_comp["lance_maximo"],
    )

    # Comentário
    adicionar_comentario(
        pncp_id=pncp_id,
        tipo="competitivo",
        texto=(
            f"Análise competitiva concluída. "
            f"Lance sugerido: R$ {resultado_comp['lance_sugerido']:,.2f} "
            f"(margem {resultado_comp['margem_sugerida_pct']:.1f}%). "
            f"Estratégia: {resultado_comp.get('estrategia', 'moderada')}. "
            f"Concorrentes: {', '.join(resultado_comp.get('concorrentes_esperados', []))}"
        ),
        autor="Agente4-Competitivo",
    )

    return resultado_comp


def executar_competitivo(limit: int = 10) -> dict:
    """Processa editais com status 'precificado'.

    Returns:
        Stats dict.
    """
    init_db()
    sincronizar_concorrentes()

    editais = get_editais_pendentes(status="precificado", limit=limit)
    log.info(f"Competitivo: {len(editais)} editais para analisar")

    resultados = {"total": len(editais), "sucesso": 0, "erro": 0}

    for edital in editais:
        pncp_id = edital["pncp_id"]
        log.info(f"Analisando competitividade: {pncp_id}")

        try:
            resultado = analisar_edital_competitivo(pncp_id)
            if resultado:
                resultados["sucesso"] += 1
                log.info(
                    f"  OK: Lance sugerido R$ {resultado['lance_sugerido']:,.2f} "
                    f"({resultado.get('estrategia', '?')})"
                )
            else:
                resultados["erro"] += 1
        except Exception as e:
            resultados["erro"] += 1
            log.error(f"  Erro: {e}")

    log.info(
        f"Competitivo concluído: {resultados['sucesso']}/{resultados['total']} OK"
    )
    return resultados


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    init_db()
    stats = executar_competitivo()
    print(f"\nResultado: {stats}")
