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
# LLM removido — usa motor_matematico (código puro)
from agente4_competitivo.concorrente_profiler import sincronizar_concorrentes
from agente4_competitivo.lance_analyzer import analisar_competitividade

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

    # 2. Enriquecimento com motor_matematico (codigo puro, zero API)
    try:
        perfis = resultado_comp.get("perfis_concorrentes", [])
        margem_sugerida = resultado_comp.get("margem_sugerida_pct", 5.0)
        piso_inex = resultado_comp.get("piso_inexequibilidade", 0)

        # Classifica concorrentes (agressivo/moderado/conservador)
        agressivos = [p for p in perfis if p.get("desconto_medio_pct", 0) > 15]
        conservadores = [p for p in perfis if p.get("desconto_medio_pct", 0) < 5]

        # Estrategia baseada em competitividade e inexequibilidade
        desconto_atual = ((valor_referencia - valor_proposta) / valor_referencia * 100) if valor_referencia else 0
        if valor_proposta < piso_inex:
            estrategia = "risco_inexequibilidade"
        elif len(agressivos) >= 3:
            estrategia = "agressiva"  # muitos agressivos, precisa descer
        elif len(conservadores) > len(agressivos):
            estrategia = "conservadora"  # mercado conservador, mantem margem
        else:
            estrategia = "moderada"

        # Riscos identificados (rule-based)
        riscos = []
        if valor_proposta < piso_inex * 1.05:
            riscos.append("Proposta próxima ao piso de inexequibilidade")
        if len(agressivos) >= 2:
            riscos.append(f"{len(agressivos)} concorrentes agressivos na regiao")
        if prazo_meses < 6:
            riscos.append("Prazo curto — dificulta diluicao de custos fixos")

        # Oportunidades
        oportunidades = []
        if not perfis:
            oportunidades.append("Edital sem histórico de concorrentes conhecidos — menor competicao")
        if desconto_atual < 5 and len(conservadores) > 0:
            oportunidades.append("Mercado conservador e proposta pouco descontada — boa margem")
        if margem_sugerida > 10:
            oportunidades.append("Margem sugerida acima de 10% — espaço para negociar")

        # Dicas negociacao
        dicas = []
        if estrategia == "agressiva":
            dicas.append("Avaliar reducao de 2-3% na proposta para competir com agressivos")
        if estrategia == "conservadora":
            dicas.append("Manter proposta, mercado aceita margens maiores")
        if len(perfis) > 5:
            dicas.append("Muitos concorrentes ativos — focar em atestados e diferenciais técnicos")

        resultado_comp["estrategia"] = estrategia
        resultado_comp["riscos"] = riscos
        resultado_comp["oportunidades"] = oportunidades
        resultado_comp["dicas_negociacao"] = dicas
        resultado_comp["justificativa"] = (
            f"Analise rule-based: {len(perfis)} concorrentes historicos "
            f"({len(agressivos)} agressivos, {len(conservadores)} conservadores). "
            f"Estrategia: {estrategia}. Desconto atual: {desconto_atual:.1f}%."
        )
        resultado_comp["_metodo"] = "motor_matematico_puro"

    except Exception as e:
        log.warning(f"Erro na analise rule-based: {e}")

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
