"""Cálculo de encargos trabalhistas — 6 módulos.

Módulos:
1. Composição da Remuneração
2. Encargos e Benefícios (2.1 13º/Férias, 2.2 GPS/FGTS, 2.3 Benefícios)
3. Provisões para Rescisão
4. Custo de Reposição do Profissional Ausente
5. Insumos Diversos (uniformes, materiais, equipamentos)
6. Custos Indiretos, Tributos e Lucro
"""
import logging

log = logging.getLogger("encargos")

SALARIO_MINIMO_2026 = 1518.00


def calcular_modulo1(
    salario_base: float,
    adicional_periculosidade: bool = False,
    adicional_insalubridade: str | None = None,
    adicional_noturno: bool = False,
    jornada: str = "44h",
    outros: float = 0,
) -> dict:
    """Módulo 1 — Composição da Remuneração."""
    total = salario_base
    perc = 0
    insalub = 0
    noturno = 0

    if adicional_periculosidade:
        perc = round(salario_base * 0.30, 2)
        total += perc

    if adicional_insalubridade:
        pcts = {"minimo": 0.10, "medio": 0.20, "maximo": 0.40}
        pct = pcts.get(adicional_insalubridade, 0)
        insalub = round(SALARIO_MINIMO_2026 * pct, 2)
        total += insalub

    if adicional_noturno:
        proporcao = 0.5 if jornada == "12x36" else 0.0
        if proporcao > 0:
            noturno = round(salario_base * 0.20 * proporcao, 2)
            total += noturno

    if outros > 0:
        total += outros

    return {
        "salario_base": salario_base,
        "adicional_periculosidade": perc,
        "adicional_insalubridade": insalub,
        "adicional_noturno": noturno,
        "total_modulo1": round(total, 2),
    }


def calcular_modulo2(
    total_modulo1: float,
    salario_base: float,
    rat_pct: float = 3.0,
    desonerado: bool = False,
    ano: int = 2026,
    **kwargs_beneficios,
) -> dict:
    """Módulo 2 — Encargos e Benefícios.

    2.1 - 13º Salário e Férias
    2.2 - GPS, FGTS e Contribuições (incide sobre M1 + 2.1)
    2.3 - Benefícios Mensais
    """
    # 2.1 - 13º e Férias
    decimo_terceiro = round(total_modulo1 / 12, 2)
    ferias_terco = round(total_modulo1 / 12 * 4 / 3, 2)
    total_21 = round(decimo_terceiro + ferias_terco, 2)

    # Base para encargos previdenciários = M1 + 13º + Férias
    base_encargos = total_modulo1 + total_21

    # 2.2 - GPS, FGTS e Contribuições
    # IMPORTANTE: Desoneração só se aplica a CNAEs específicos (Anexo Lei 12.546).
    # Para serviços de MOD (cessão de mão de obra), verificar se o CNAE da empresa
    # está no Anexo. Na dúvida, usar INSS padrão de 20%.
    # A Lei 14.973/2024 prevê reoneração gradual: 2025=25%, 2026=50%, 2027=75%, 2028=100%
    if desonerado and ano == 2025:
        inss_pct = 0.05   # 25% de 20%
    elif desonerado and ano == 2026:
        inss_pct = 0.10   # 50% de 20%
    elif desonerado and ano == 2027:
        inss_pct = 0.15   # 75% de 20%
    else:
        inss_pct = 0.20   # Padrão: sem desoneração

    sat_rat_pct = rat_pct / 100
    sal_educacao_pct = 0.025
    sesc_pct = 0.015
    senac_pct = 0.01
    sebrae_pct = 0.006
    incra_pct = 0.002
    fgts_pct = 0.08

    inss = round(base_encargos * inss_pct, 2)
    sal_educacao = round(base_encargos * sal_educacao_pct, 2)
    sat_rat = round(base_encargos * sat_rat_pct, 2)
    sesc = round(base_encargos * sesc_pct, 2)
    senac = round(base_encargos * senac_pct, 2)
    sebrae = round(base_encargos * sebrae_pct, 2)
    incra = round(base_encargos * incra_pct, 2)
    fgts = round(base_encargos * fgts_pct, 2)

    total_22 = round(inss + sal_educacao + sat_rat + sesc + senac + sebrae + incra + fgts, 2)

    submodulo_2_1 = {
        "inss": inss, "inss_pct": inss_pct,
        "sal_educacao": sal_educacao, "sal_educacao_pct": sal_educacao_pct,
        "sat_rat": sat_rat, "sat_rat_pct": sat_rat_pct,
        "sesc": sesc, "sesc_pct": sesc_pct,
        "senac": senac, "senac_pct": senac_pct,
        "sebrae": sebrae, "sebrae_pct": sebrae_pct,
        "incra": incra, "incra_pct": incra_pct,
        "fgts": fgts, "fgts_pct": fgts_pct,
        "total_submodulo_2_1": total_22,
        "percentual_total": round(total_22 / base_encargos * 100, 2) if base_encargos > 0 else 0,
    }

    # 2.3 - Benefícios
    submodulo_2_2 = calcular_beneficios(salario_base, **kwargs_beneficios)
    total_23 = submodulo_2_2["total_submodulo_2_2"]

    total_m2 = round(total_21 + total_22 + total_23, 2)

    return {
        "decimo_terceiro": decimo_terceiro,
        "ferias_terco": ferias_terco,
        "total_21": total_21,
        "submodulo_2_1": submodulo_2_1,
        "submodulo_2_2": submodulo_2_2,
        "total_modulo2": total_m2,
    }


def calcular_beneficios(
    salario_base: float,
    vale_transporte_valor: float = 230.00,
    vale_alimentacao_dia: float = 25.00,
    dias_alimentacao: int = 22,
    desconto_vt_pct: float = 6.0,
    desconto_va_pct: float = 10.0,
    cesta_basica: float = 0,
    plano_saude: float = 0,
    seguro_vida: float = 0,
    outros_beneficios: float = 0,
    **kwargs,
) -> dict:
    """Submódulo 2.3 — Benefícios mensais."""
    desconto_vt = salario_base * desconto_vt_pct / 100
    vt = round(max(vale_transporte_valor - desconto_vt, 0), 2)

    va_bruto = vale_alimentacao_dia * dias_alimentacao
    desconto_va = va_bruto * desconto_va_pct / 100
    va = round(va_bruto - desconto_va, 2)

    total = vt + va + cesta_basica + plano_saude + seguro_vida + outros_beneficios

    return {
        "vale_transporte": vt,
        "vale_alimentacao": va,
        "cesta_basica": round(cesta_basica, 2),
        "plano_saude": round(plano_saude, 2),
        "seguro_vida": round(seguro_vida, 2),
        "total_submodulo_2_2": round(total, 2),
    }


def calcular_modulo3(total_modulo1: float, fgts_pct: float = 8.0) -> dict:
    """Módulo 3 — Provisões para Rescisão.

    Baseado na planilha SEFAZ padrão:
    A - Aviso prévio indenizado
    B - Incid. FGTS s/ API
    C - Multa FGTS API
    D - Aviso prévio trabalhado
    E - Incid. Submód 2.2 s/ APT
    F - Multa FGTS APT
    """
    # Aviso prévio indenizado: ~1.94% (probabilidade de demissão × 1 mês)
    api_val = round(total_modulo1 * 0.01940, 2)

    # Incidência FGTS sobre API (8%)
    incid_fgts_api = round(api_val * fgts_pct / 100, 2)

    # Multa FGTS sobre API (50% × FGTS mensal × coeficiente)
    fgts_mensal = total_modulo1 * fgts_pct / 100
    multa_fgts_api = round(fgts_mensal * 0.50 * 0.01851, 2)

    # Aviso prévio trabalhado: ~0.4525% do salário
    apt_val = round(total_modulo1 * 0.004525, 2)

    # Incidência Submód 2.2 sobre APT (~35.8% de encargos)
    incid_submod_apt = round(apt_val * 0.358, 2)

    # Multa FGTS sobre APT (mesmo coeficiente)
    multa_fgts_apt = round(fgts_mensal * 0.50 * 0.01851, 2)

    total = api_val + incid_fgts_api + multa_fgts_api + apt_val + incid_submod_apt + multa_fgts_apt

    return {
        "aviso_previo_indenizado": api_val,
        "incid_fgts_api": incid_fgts_api,
        "multa_fgts_api": multa_fgts_api,
        "aviso_previo_trabalhado": apt_val,
        "incid_submod_apt": incid_submod_apt,
        "multa_fgts_apt": multa_fgts_apt,
        "total_modulo3": round(total, 2),
    }


def calcular_modulo4(total_modulo1: float, jornada: str = "44h") -> dict:
    """Módulo 4 — Custo de Reposição do Profissional Ausente.

    4.1 - Ausências Legais
    4.2 - Intrajornada
    """
    custo_diario = total_modulo1 / 30

    ferias_substituto = round(total_modulo1 / 12, 2)
    ausencias_legais = round(custo_diario * 2.96 / 12, 2)  # ~2.96 dias/ano
    licenca_paternidade = round(custo_diario * 0.10 / 12, 2)
    afastamento_maternidade = round(custo_diario * 2.37 / 12, 2)

    total_41 = round(ferias_substituto + ausencias_legais + licenca_paternidade + afastamento_maternidade, 2)

    # Intrajornada (0 para jornada normal, pode ter valor para 12x36)
    intrajornada = 0

    total = round(total_41 + intrajornada, 2)

    return {
        "ferias_substituto": ferias_substituto,
        "ausencias_legais": ausencias_legais,
        "licenca_paternidade": licenca_paternidade,
        "afastamento_maternidade": afastamento_maternidade,
        "intrajornada": intrajornada,
        "total_modulo4": total,
    }


def calcular_modulo5_insumos(
    uniformes: float = 90.0,
    materiais: float = 0,
    equipamentos: float = 0,
) -> dict:
    """Módulo 5 — Insumos Diversos."""
    total = uniformes + materiais + equipamentos
    return {
        "uniformes": round(uniformes, 2),
        "materiais": round(materiais, 2),
        "equipamentos": round(equipamentos, 2),
        "total_modulo5": round(total, 2),
    }


def calcular_modulo6(
    subtotal_m1_m5: float,
    ci_pct: float = 3.0,
    lucro_pct: float = 3.0,
    pis_pct: float = 0.05,
    cofins_pct: float = 4.15,
    iss_pct: float = 2.0,
) -> dict:
    """Módulo 6 — Custos Indiretos, Tributos e Lucro.

    Tributos calculados "por dentro" (sobre o preço de venda).
    """
    ci = round(subtotal_m1_m5 * ci_pct / 100, 2)
    lucro = round(subtotal_m1_m5 * lucro_pct / 100, 2)

    # Tributos por dentro: base = subtotal + CI + lucro / (1 - aliquota_tributos)
    tributos_total_pct = (pis_pct + cofins_pct + iss_pct) / 100
    base_antes_tributos = subtotal_m1_m5 + ci + lucro
    valor_com_tributos = base_antes_tributos / (1 - tributos_total_pct)

    tributos_total = round(valor_com_tributos - base_antes_tributos, 2)
    pis = round(valor_com_tributos * pis_pct / 100, 2)
    cofins = round(valor_com_tributos * cofins_pct / 100, 2)
    iss = round(valor_com_tributos * iss_pct / 100, 2)

    total = round(ci + lucro + tributos_total, 2)

    return {
        "custos_indiretos": ci,
        "ci_pct": ci_pct / 100,
        "lucro": lucro,
        "lucro_pct": lucro_pct / 100,
        "tributos": tributos_total,
        "tributos_detalhe": {
            "pis": pis, "pis_pct": pis_pct / 100,
            "cofins": cofins, "cofins_pct": cofins_pct / 100,
            "iss": iss, "iss_pct": iss_pct / 100,
        },
        "total_modulo6": total,
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
    lucro_pct: float = 3.0,
    tributos_pct: float = 6.20,
    pis_pct: float = 0.05,
    cofins_pct: float = 4.15,
    iss_pct: float = 2.0,
    uniformes: float = 90.0,
    materiais: float = 0,
    equipamentos: float = 0,
    **kwargs_beneficios,
) -> dict:
    """Calcula o custo total mensal de um posto — 6 módulos."""
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

    m5 = calcular_modulo5_insumos(uniformes, materiais, equipamentos)

    subtotal = (
        m1["total_modulo1"] + m2["total_modulo2"]
        + m3["total_modulo3"] + m4["total_modulo4"]
        + m5["total_modulo5"]
    )

    m6 = calcular_modulo6(subtotal, ci_pct, lucro_pct, pis_pct, cofins_pct, iss_pct)

    valor_mensal = round(subtotal + m6["total_modulo6"], 2)

    return {
        "modulo1": m1,
        "modulo2": m2,
        "modulo3": m3,
        "modulo4": m4,
        "modulo5": m5,
        "modulo6": m6,
        "subtotal_m1_m4": round(m1["total_modulo1"] + m2["total_modulo2"] + m3["total_modulo3"] + m4["total_modulo4"], 2),
        "subtotal_m1_m5": round(subtotal, 2),
        "valor_mensal_posto": valor_mensal,
    }
