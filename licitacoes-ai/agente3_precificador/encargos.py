"""Cálculo de encargos trabalhistas conforme IN 05/2017 do MPOG.

Módulos:
1. Composição da Remuneração
2. Encargos e Benefícios Mensais (2.1 Previdenciários + 2.2 Benefícios)
3. Provisões para Rescisão
4. Custo de Reposição do Profissional Ausente
5. Custos Indiretos, Tributos e Lucro
"""
import logging

log = logging.getLogger("encargos")

SALARIO_MINIMO_2026 = 1518.00  # Atualizar conforme decreto


def calcular_modulo1(
    salario_base: float,
    adicional_periculosidade: bool = False,
    adicional_insalubridade: str | None = None,  # "minimo", "medio", "maximo"
    adicional_noturno: bool = False,
    jornada: str = "44h",
    outros: float = 0,
) -> dict:
    """Módulo 1 — Composição da Remuneração."""
    m1 = {"salario_base": salario_base}
    total = salario_base

    # 1.2 Periculosidade (30% do salário)
    if adicional_periculosidade:
        val = salario_base * 0.30
        m1["periculosidade"] = round(val, 2)
        total += val

    # 1.3 Insalubridade (% do salário mínimo)
    if adicional_insalubridade:
        pcts = {"minimo": 0.10, "medio": 0.20, "maximo": 0.40}
        pct = pcts.get(adicional_insalubridade, 0)
        val = SALARIO_MINIMO_2026 * pct
        m1["insalubridade"] = round(val, 2)
        total += val

    # 1.4 Adicional noturno (20% sobre hora noturna)
    if adicional_noturno:
        # Simplificação: 20% sobre salário proporcional às horas noturnas
        # Assume ~50% da jornada em período noturno para 12x36
        proporcao = 0.5 if jornada == "12x36" else 0.0
        if proporcao > 0:
            val = salario_base * 0.20 * proporcao
            m1["adicional_noturno"] = round(val, 2)
            total += val

    if outros > 0:
        m1["outros"] = round(outros, 2)
        total += outros

    m1["total_modulo1"] = round(total, 2)
    return m1


def calcular_submodulo_2_1(
    total_modulo1: float,
    rat_pct: float = 3.0,  # SAT/RAT ajustado pelo FAP (1% a 3%)
    desonerado: bool = False,
    ano: int = 2026,
) -> dict:
    """Submódulo 2.1 — Encargos previdenciários e FGTS.

    Para 2026 com desoneração gradual (Lei 14.973/2024):
    - 2026: 10% CPRB + 10% INSS patronal (transição)
    """
    encargos = {}

    if desonerado:
        # Transição 2026: metade INSS, metade CPRB
        if ano == 2025:
            encargos["inss_patronal"] = 0  # Substituído por CPRB
            encargos["cprb_nota"] = "CPRB cobrado sobre receita bruta (5%)"
        elif ano == 2026:
            encargos["inss_patronal"] = round(total_modulo1 * 0.10, 2)
            encargos["cprb_nota"] = "Transição: 10% INSS + 10% CPRB sobre receita"
        elif ano == 2027:
            encargos["inss_patronal"] = round(total_modulo1 * 0.15, 2)
        else:
            encargos["inss_patronal"] = round(total_modulo1 * 0.20, 2)
    else:
        encargos["inss_patronal"] = round(total_modulo1 * 0.20, 2)

    encargos["sesi_sesc"] = round(total_modulo1 * 0.015, 2)
    encargos["senai_senac"] = round(total_modulo1 * 0.01, 2)
    encargos["incra"] = round(total_modulo1 * 0.002, 2)
    encargos["salario_educacao"] = round(total_modulo1 * 0.025, 2)
    encargos["sat_rat"] = round(total_modulo1 * rat_pct / 100, 2)
    encargos["sebrae"] = round(total_modulo1 * 0.006, 2)
    encargos["fgts"] = round(total_modulo1 * 0.08, 2)

    total = sum(v for v in encargos.values() if isinstance(v, (int, float)))
    encargos["total_submodulo_2_1"] = round(total, 2)

    # Percentual total sobre módulo 1
    pct = (total / total_modulo1 * 100) if total_modulo1 > 0 else 0
    encargos["percentual_total"] = round(pct, 2)

    return encargos


def calcular_submodulo_2_2(
    salario_base: float,
    vale_transporte_valor: float = 230.00,  # Valor médio mensal VT
    vale_alimentacao_dia: float = 34.00,
    dias_alimentacao: int = 22,
    desconto_vt_pct: float = 6.0,
    desconto_va_pct: float = 1.0,
    cesta_basica: float = 183.26,
    plano_saude: float = 0,  # 0 se não exigido
    seguro_vida: float = 15.00,
    outros_beneficios: float = 0,
) -> dict:
    """Submódulo 2.2 — Benefícios mensais."""
    beneficios = {}

    # Vale transporte (valor - 6% do salário)
    desconto_vt = salario_base * desconto_vt_pct / 100
    vt_liquido = max(vale_transporte_valor - desconto_vt, 0)
    beneficios["vale_transporte"] = round(vt_liquido, 2)

    # Vale alimentação
    va_bruto = vale_alimentacao_dia * dias_alimentacao
    desconto_va = va_bruto * desconto_va_pct / 100
    beneficios["vale_alimentacao"] = round(va_bruto - desconto_va, 2)

    # Cesta básica
    beneficios["cesta_basica"] = round(cesta_basica, 2)

    # Plano de saúde
    if plano_saude > 0:
        beneficios["plano_saude"] = round(plano_saude, 2)

    # Seguro de vida
    beneficios["seguro_vida"] = round(seguro_vida, 2)

    if outros_beneficios > 0:
        beneficios["outros"] = round(outros_beneficios, 2)

    total = sum(v for v in beneficios.values() if isinstance(v, (int, float)))
    beneficios["total_submodulo_2_2"] = round(total, 2)

    return beneficios


def calcular_modulo2(
    total_modulo1: float,
    salario_base: float,
    rat_pct: float = 3.0,
    desonerado: bool = False,
    ano: int = 2026,
    **kwargs_beneficios,
) -> dict:
    """Módulo 2 — Encargos e Benefícios Mensais."""
    # 13º salário
    decimo_terceiro = round(total_modulo1 / 12, 2)

    # Férias + 1/3
    ferias = round(total_modulo1 / 12 * 4 / 3, 2)

    sub_2_1 = calcular_submodulo_2_1(total_modulo1, rat_pct, desonerado, ano)
    sub_2_2 = calcular_submodulo_2_2(salario_base, **kwargs_beneficios)

    # Incidência dos encargos previdenciários sobre 13o e férias
    pct_prev = sub_2_1["percentual_total"] / 100
    incidencia_13 = round(decimo_terceiro * pct_prev, 2)
    incidencia_ferias = round(ferias * pct_prev, 2)

    total = (
        decimo_terceiro + ferias
        + sub_2_1["total_submodulo_2_1"]
        + sub_2_2["total_submodulo_2_2"]
        + incidencia_13 + incidencia_ferias
    )

    return {
        "decimo_terceiro": decimo_terceiro,
        "ferias_terco": ferias,
        "incidencia_13_prev": incidencia_13,
        "incidencia_ferias_prev": incidencia_ferias,
        "submodulo_2_1": sub_2_1,
        "submodulo_2_2": sub_2_2,
        "total_modulo2": round(total, 2),
    }


def calcular_modulo3(total_modulo1: float, fgts_pct: float = 8.0) -> dict:
    """Módulo 3 — Provisões para Rescisão."""
    # Aviso prévio indenizado (estimativa: 1 mês / 12 * probabilidade ~5%)
    aviso_indenizado = round(total_modulo1 * 0.0042, 2)  # ~5% chance × 1/12

    # Incidência FGTS sobre aviso prévio indenizado
    fgts_aviso = round(aviso_indenizado * fgts_pct / 100, 2)

    # Multa FGTS rescisória (40% + 10% contrib social)
    # Base: 8% do salário × 12 meses × 50%
    multa_fgts = round(total_modulo1 * fgts_pct / 100 * 12 * 0.50 / 12 * 0.0333, 2)

    # Aviso prévio trabalhado
    aviso_trabalhado = round(total_modulo1 * 7 / 30 / 12, 2)

    total = aviso_indenizado + fgts_aviso + multa_fgts + aviso_trabalhado
    return {
        "aviso_previo_indenizado": aviso_indenizado,
        "fgts_sobre_aviso": fgts_aviso,
        "multa_fgts_rescisoria": multa_fgts,
        "aviso_previo_trabalhado": aviso_trabalhado,
        "total_modulo3": round(total, 2),
    }


def calcular_modulo4(total_modulo1: float, jornada: str = "44h") -> dict:
    """Módulo 4 — Custo de Reposição do Profissional Ausente."""
    custo_diario = total_modulo1 / 30

    # Estimativas de dias de ausência por ano
    ferias_substituto = round(custo_diario * 30 / 12, 2)  # 30 dias/12 meses
    ausencias_legais = round(custo_diario * 5 / 12, 2)  # ~5 dias/ano
    licenca_paternidade = round(custo_diario * 0.5 / 12, 2)
    acidente_trabalho = round(custo_diario * 3 / 12, 2)  # ~3 dias/ano
    afastamento_maternidade = round(custo_diario * 0.4 / 12, 2)

    total = (
        ferias_substituto + ausencias_legais
        + licenca_paternidade + acidente_trabalho
        + afastamento_maternidade
    )

    return {
        "ferias_substituto": ferias_substituto,
        "ausencias_legais": ausencias_legais,
        "licenca_paternidade": licenca_paternidade,
        "acidente_trabalho": acidente_trabalho,
        "afastamento_maternidade": afastamento_maternidade,
        "total_modulo4": round(total, 2),
    }


def calcular_modulo5(
    subtotal_modulos_1_4: float,
    ci_pct: float = 3.0,
    lucro_pct: float = 5.0,
    tributos_pct: float = 9.25,
) -> dict:
    """Módulo 5 — Custos Indiretos, Tributos e Lucro."""
    custos_indiretos = round(subtotal_modulos_1_4 * ci_pct / 100, 2)
    lucro = round(subtotal_modulos_1_4 * lucro_pct / 100, 2)

    # Tributos incidem sobre o valor total (incluindo CI e lucro)
    base_tributos = subtotal_modulos_1_4 + custos_indiretos + lucro
    tributos = round(base_tributos * tributos_pct / 100 / (1 - tributos_pct / 100), 2)

    total = custos_indiretos + lucro + tributos

    return {
        "custos_indiretos": custos_indiretos,
        "ci_pct": ci_pct,
        "lucro": lucro,
        "lucro_pct": lucro_pct,
        "tributos": tributos,
        "tributos_pct": tributos_pct,
        "total_modulo5": round(total, 2),
    }


def calcular_posto_completo(
    salario_base: float,
    jornada: str = "44h",
    adicional_periculosidade: bool = False,
    adicional_insalubridade: str | None = None,
    adicional_noturno: bool = False,
    rat_pct: float = 3.0,
    desonerado: bool = False,
    ci_pct: float = 3.0,
    lucro_pct: float = 5.0,
    tributos_pct: float = 9.25,
    **kwargs_beneficios,
) -> dict:
    """Calcula o custo total mensal de um posto de trabalho."""
    m1 = calcular_modulo1(
        salario_base, adicional_periculosidade,
        adicional_insalubridade, adicional_noturno, jornada,
    )

    m2 = calcular_modulo2(
        m1["total_modulo1"], salario_base,
        rat_pct, desonerado, **kwargs_beneficios,
    )

    m3 = calcular_modulo3(m1["total_modulo1"])
    m4 = calcular_modulo4(m1["total_modulo1"], jornada)

    subtotal = m1["total_modulo1"] + m2["total_modulo2"] + m3["total_modulo3"] + m4["total_modulo4"]

    m5 = calcular_modulo5(subtotal, ci_pct, lucro_pct, tributos_pct)

    valor_mensal = round(subtotal + m5["total_modulo5"], 2)

    return {
        "modulo1": m1,
        "modulo2": m2,
        "modulo3": m3,
        "modulo4": m4,
        "modulo5": m5,
        "subtotal_m1_m4": round(subtotal, 2),
        "valor_mensal_posto": valor_mensal,
    }
