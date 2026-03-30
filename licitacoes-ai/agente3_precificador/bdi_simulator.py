"""Simulador de BDI e margem."""
import logging

log = logging.getLogger("bdi_simulator")

# Piso de inexequibilidade: Art. 59 §4 da Lei 14.133/2021
PISO_INEXEQUIBILIDADE_PCT = 75.0


def calcular_bdi(ci_pct: float, lucro_pct: float, tributos_pct: float) -> float:
    """Calcula BDI: (1+CI)*(1+Lucro)/(1-Tributos) - 1"""
    bdi = (1 + ci_pct / 100) * (1 + lucro_pct / 100) / (1 - tributos_pct / 100) - 1
    return round(bdi * 100, 2)


def simular_cenarios(
    custo_direto_mensal: float,
    valor_referencia_mensal: float,
    prazo_meses: int = 12,
    tributos_pct: float = 9.25,
) -> list[dict]:
    """Simula 3 cenários de BDI: agressivo, competitivo, conservador."""
    cenarios_config = [
        {"nome": "ultra_agressivo", "ci": 1.0, "lucro": 1.0},
        {"nome": "agressivo", "ci": 2.0, "lucro": 2.0},
        {"nome": "competitivo", "ci": 3.0, "lucro": 3.0},
        {"nome": "conservador", "ci": 5.0, "lucro": 5.0},
    ]

    resultados = []
    for c in cenarios_config:
        bdi_pct = calcular_bdi(c["ci"], c["lucro"], tributos_pct)
        valor_mensal = round(custo_direto_mensal * (1 + bdi_pct / 100), 2)
        valor_global = round(valor_mensal * prazo_meses, 2)

        desconto = 0
        if valor_referencia_mensal > 0:
            desconto = round(
                (1 - valor_mensal / valor_referencia_mensal) * 100, 2
            )

        piso = valor_referencia_mensal * prazo_meses * PISO_INEXEQUIBILIDADE_PCT / 100
        acima_piso = valor_global >= piso

        resultados.append({
            "cenario": c["nome"],
            "ci_pct": c["ci"],
            "lucro_pct": c["lucro"],
            "tributos_pct": tributos_pct,
            "bdi_pct": bdi_pct,
            "valor_mensal": valor_mensal,
            "valor_global": valor_global,
            "desconto_sobre_referencia_pct": desconto,
            "acima_inexequibilidade": acima_piso,
        })

        if not acima_piso:
            log.warning(
                f"ALERTA: Cenário '{c['nome']}' abaixo do piso de inexequibilidade! "
                f"(R$ {valor_global:,.2f} < R$ {piso:,.2f})"
            )

    return resultados
