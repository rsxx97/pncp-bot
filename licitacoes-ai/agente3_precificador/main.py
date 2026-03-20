"""Agente 3 — Precificador: orquestra cálculo de custos IN 05/2017."""
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
from agente3_precificador.cct_manager import (
    get_piso_salarial, get_beneficios, importar_ccts_diretorio,
)
from agente3_precificador.encargos import calcular_posto_completo
from agente3_precificador.tributos import calcular_tributos
from agente3_precificador.bdi_simulator import simular_cenarios
from agente3_precificador.planilha_builder import gerar_xlsx
from agente3_precificador.prompts import (
    SYSTEM_EXTRAIR_POSTOS, PROMPT_EXTRAIR_POSTOS,
)

log = logging.getLogger("agente3_precificador")

PLANILHAS_DIR = DATA_DIR / "planilhas"


def _extrair_postos_llm(edital: dict, analise: dict) -> dict:
    """Usa Claude para extrair postos e parâmetros do edital analisado."""
    postos_analise = analise.get("postos", [])
    postos_texto = ""
    if postos_analise:
        for p in postos_analise:
            if isinstance(p, dict):
                postos_texto += f"- {p.get('funcao', '?')}: {p.get('quantidade', 1)} postos, jornada {p.get('jornada', '44h')}\n"
            else:
                postos_texto += f"- {p}\n"
    else:
        postos_texto = "Não identificados na análise prévia."

    requisitos = analise.get("requisitos_habilitacao", [])
    requisitos_texto = "\n".join(f"- {r}" for r in requisitos) if requisitos else "Não especificados."

    prompt = PROMPT_EXTRAIR_POSTOS.format(
        objeto=edital.get("objeto", ""),
        valor_estimado=f"{edital.get('valor_estimado', 0):,.2f}",
        municipio=edital.get("municipio", "Rio de Janeiro"),
        uf=edital.get("uf", "RJ"),
        empresa_sugerida=edital.get("empresa_sugerida", "manutec"),
        prazo_meses=analise.get("prazo_contrato_meses", 12) or 12,
        postos_texto=postos_texto,
        requisitos_texto=requisitos_texto,
        regime_contratacao=analise.get("regime_contratacao", ""),
        cct_aplicavel=analise.get("cct_aplicavel", ""),
        local_prestacao=analise.get("local_prestacao", ""),
        observacoes="",
    )

    return ask_claude_json(
        system=SYSTEM_EXTRAIR_POSTOS,
        user=prompt,
        max_tokens=3000,
        agente="precificador",
        pncp_id=edital.get("pncp_id"),
    )


def _resolver_salario(funcao: str, salario_edital: float | None,
                      sindicato: str, uf: str) -> float:
    """Determina salário: usa edital se fornecido, senão piso CCT, senão default."""
    if salario_edital and salario_edital > 0:
        return salario_edital

    piso = get_piso_salarial(sindicato, uf, funcao)
    if piso:
        return piso

    # Default: salário mínimo 2026
    log.warning(f"Sem piso para {funcao} ({sindicato}/{uf}). Usando salário mínimo.")
    return 1518.00


def _montar_kwargs_beneficios(sindicato: str, uf: str, params: dict) -> dict:
    """Monta kwargs de benefícios a partir da CCT e parâmetros."""
    beneficios = get_beneficios(sindicato, uf)
    kwargs = {}

    vt = beneficios.get("vale_transporte", {})
    if vt:
        kwargs["desconto_vt_pct"] = vt.get("desconto_empregado_pct", 6.0)

    va = beneficios.get("vale_alimentacao", {})
    if va:
        kwargs["vale_alimentacao_dia"] = va.get("valor_dia", 34.00)
        kwargs["dias_alimentacao"] = va.get("dias_mes", 22)
        kwargs["desconto_va_pct"] = va.get("desconto_empregado_pct", 1.0)

    cb = beneficios.get("cesta_basica", {})
    if cb:
        kwargs["cesta_basica"] = cb.get("valor_mensal", 183.26)

    sv = beneficios.get("seguro_vida", {})
    if sv:
        kwargs["seguro_vida"] = sv.get("valor_mensal_por_empregado", 15.00)

    if params.get("plano_saude_obrigatorio"):
        kwargs["plano_saude"] = params.get("valor_plano_saude", 200.00)

    return kwargs


def precificar_edital(pncp_id: str) -> dict | None:
    """Pipeline completo de precificação para um edital.

    Fluxo:
    1. Carrega edital e análise do banco
    2. Extrai postos via LLM
    3. Para cada posto: resolve salário (CCT/edital) + calcula módulos 1-5
    4. Simula BDI (3 cenários)
    5. Gera planilha .xlsx
    6. Atualiza banco com resultado

    Returns:
        Dict com resultado ou None se falhar.
    """
    edital = get_edital(pncp_id)
    if not edital:
        log.error(f"Edital {pncp_id} não encontrado no banco.")
        return None

    analise_raw = edital.get("analise_json")
    if not analise_raw:
        log.warning(f"Edital {pncp_id} sem análise prévia. Usando dados básicos.")
        analise = {}
    else:
        analise = json.loads(analise_raw) if isinstance(analise_raw, str) else analise_raw

    # 1. Extrair postos via LLM
    try:
        dados_postos = _extrair_postos_llm(edital, analise)
    except Exception as e:
        log.error(f"Erro ao extrair postos: {e}")
        atualizar_status_edital(pncp_id, "erro_precificacao", motivo_nogo=str(e))
        return None

    postos_raw = dados_postos.get("postos", [])
    params = dados_postos.get("parametros", {})

    if not postos_raw:
        log.warning(f"Nenhum posto extraído para {pncp_id}")
        atualizar_status_edital(pncp_id, "erro_precificacao",
                                motivo_nogo="Nenhum posto de trabalho identificado")
        return None

    sindicato = params.get("sindicato_sugerido", "SEAC-RJ")
    uf = params.get("uf", edital.get("uf", "RJ"))
    prazo_meses = params.get("prazo_meses", 12) or 12
    desonerado = params.get("desonerado", False)
    rat_pct = params.get("rat_pct", 3.0)

    # Tributos
    regime = params.get("regime_tributario", "lucro_real")
    municipio = params.get("municipio", edital.get("municipio", "Rio de Janeiro"))
    tributos_info = calcular_tributos(regime, municipio)
    tributos_pct = tributos_info["total_pct"]

    # Cenários de CI/Lucro (usaremos competitivo como base da planilha)
    ci_pct = 3.0
    lucro_pct = 3.0

    # 2. Calcular cada posto
    postos_calculados = []
    kwargs_beneficios = _montar_kwargs_beneficios(sindicato, uf, params)

    for posto_raw in postos_raw:
        funcao = posto_raw.get("funcao", "servente_limpeza")
        quantidade = posto_raw.get("quantidade", 1)

        salario = _resolver_salario(
            funcao, posto_raw.get("salario_edital"), sindicato, uf
        )

        resultado_posto = calcular_posto_completo(
            salario_base=salario,
            jornada=posto_raw.get("jornada", "44h"),
            adicional_periculosidade=posto_raw.get("periculosidade", False),
            adicional_insalubridade=posto_raw.get("insalubridade"),
            adicional_noturno=posto_raw.get("noturno", False),
            rat_pct=rat_pct,
            desonerado=desonerado,
            ci_pct=ci_pct,
            lucro_pct=lucro_pct,
            tributos_pct=tributos_pct,
            **kwargs_beneficios,
        )

        resultado_posto["nome"] = posto_raw.get("funcao_display", funcao.replace("_", " ").title())
        resultado_posto["funcao"] = funcao
        resultado_posto["quantidade"] = quantidade
        resultado_posto["salario_base"] = salario

        postos_calculados.append(resultado_posto)
        log.info(
            f"  Posto {resultado_posto['nome']}: "
            f"R$ {resultado_posto['valor_mensal_posto']:,.2f}/mês × {quantidade}"
        )

    # 3. Simulação BDI
    custo_direto_total = sum(
        p["subtotal_m1_m4"] * p["quantidade"] for p in postos_calculados
    )
    valor_ref_mensal = (edital.get("valor_estimado") or 0) / prazo_meses if prazo_meses > 0 else 0

    cenarios_bdi = simular_cenarios(
        custo_direto_mensal=custo_direto_total,
        valor_referencia_mensal=valor_ref_mensal,
        prazo_meses=prazo_meses,
        tributos_pct=tributos_pct,
    )

    # 4. Gerar planilha
    PLANILHAS_DIR.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"planilha_{pncp_id.replace('/', '_').replace('-', '_')}.xlsx"
    output_path = PLANILHAS_DIR / nome_arquivo

    try:
        gerar_xlsx(
            postos=postos_calculados,
            cenarios_bdi=cenarios_bdi,
            valor_referencia=edital.get("valor_estimado"),
            prazo_meses=prazo_meses,
            output_path=output_path,
        )
        log.info(f"Planilha gerada: {output_path}")
    except Exception as e:
        log.error(f"Erro ao gerar planilha: {e}")
        output_path = None

    # 5. Calcular valor proposta (cenário competitivo)
    cenario_competitivo = next(
        (c for c in cenarios_bdi if c["cenario"] == "competitivo"), cenarios_bdi[0]
    )
    valor_proposta = cenario_competitivo["valor_global"]
    margem = cenario_competitivo.get("desconto_sobre_referencia_pct", 0)
    bdi = cenario_competitivo["bdi_pct"]

    # 6. Atualizar banco
    atualizar_status_edital(
        pncp_id,
        status="precificado",
        planilha_path=str(output_path) if output_path else None,
        valor_proposta=valor_proposta,
        margem_percentual=margem,
        bdi_percentual=bdi,
    )

    # Comentário automático
    resumo_postos = ", ".join(
        f"{p['nome']} ×{p['quantidade']}" for p in postos_calculados
    )
    adicionar_comentario(
        pncp_id=pncp_id,
        tipo="precificacao",
        texto=(
            f"Precificação concluída. Postos: {resumo_postos}. "
            f"Valor proposta (competitivo): R$ {valor_proposta:,.2f}. "
            f"BDI: {bdi:.2f}%. Margem: {margem:.1f}%."
        ),
        autor="Agente3-Precificador",
    )

    return {
        "pncp_id": pncp_id,
        "postos": postos_calculados,
        "cenarios_bdi": cenarios_bdi,
        "valor_proposta": valor_proposta,
        "margem_pct": margem,
        "bdi_pct": bdi,
        "planilha_path": str(output_path) if output_path else None,
        "tributos": tributos_info,
        "parametros": params,
    }


def executar_precificador(limit: int = 10) -> dict:
    """Processa editais com status 'analisado' e parecer 'go' ou 'go_com_ressalvas'.

    Returns:
        Stats dict com totais processados.
    """
    init_db()
    importar_ccts_diretorio()

    editais = get_editais_pendentes(status="analisado", limit=limit)

    # Filtra apenas os com parecer positivo
    editais_go = []
    for e in editais:
        parecer = e.get("parecer", "")
        if parecer in ("go", "go_com_ressalvas"):
            editais_go.append(e)

    log.info(f"Precificador: {len(editais_go)} editais para processar")

    resultados = {"total": len(editais_go), "sucesso": 0, "erro": 0}

    for edital in editais_go:
        pncp_id = edital["pncp_id"]
        log.info(f"Precificando: {pncp_id}")

        try:
            resultado = precificar_edital(pncp_id)
            if resultado:
                resultados["sucesso"] += 1
                log.info(
                    f"  OK: R$ {resultado['valor_proposta']:,.2f} "
                    f"(BDI {resultado['bdi_pct']:.2f}%)"
                )
            else:
                resultados["erro"] += 1
        except Exception as e:
            resultados["erro"] += 1
            log.error(f"  Erro: {e}")
            atualizar_status_edital(pncp_id, "erro_precificacao", motivo_nogo=str(e))

    log.info(
        f"Precificador concluído: {resultados['sucesso']}/{resultados['total']} OK, "
        f"{resultados['erro']} erros"
    )
    return resultados


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    init_db()
    stats = executar_precificador()
    print(f"\nResultado: {stats}")
