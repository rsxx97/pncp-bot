"""Cálculo tributário por regime e município."""
import logging

log = logging.getLogger("tributos")

# ISS por município (valores padrão, ajustáveis)
ISS_MUNICIPIO = {
    "Rio de Janeiro": 2.0,
    "Niterói": 2.0,
    "São Gonçalo": 3.0,
    "Maricá": 2.0,
    "Angra dos Reis": 3.0,
    "Petrópolis": 3.0,
    "Volta Redonda": 3.0,
    "São Paulo": 2.0,
    "Brasília": 2.0,
}

DEFAULT_ISS = 2.0  # Quando município não está na tabela


def get_iss(municipio: str) -> float:
    """Retorna alíquota ISS do município."""
    if not municipio:
        return DEFAULT_ISS
    # Busca parcial
    mun_lower = municipio.lower()
    for k, v in ISS_MUNICIPIO.items():
        if k.lower() in mun_lower or mun_lower in k.lower():
            return v
    return DEFAULT_ISS


def calcular_tributos_lucro_real(
    municipio: str = "Rio de Janeiro",
    pis_efetivo_pct: float = 1.0,
    cofins_efetivo_pct: float = 4.5,
) -> dict:
    """Lucro Real (não cumulativo) — regime padrão do grupo.

    PIS/COFINS não cumulativo permite créditos sobre insumos.
    Taxa efetiva após créditos: geralmente entre 4% e 7%.
    """
    iss = get_iss(municipio)
    total = pis_efetivo_pct + cofins_efetivo_pct + iss

    return {
        "regime": "lucro_real",
        "pis_pct": pis_efetivo_pct,
        "pis_nota": f"Nominal 1.65%, efetivo {pis_efetivo_pct}% após créditos",
        "cofins_pct": cofins_efetivo_pct,
        "cofins_nota": f"Nominal 7.6%, efetivo {cofins_efetivo_pct}% após créditos",
        "iss_pct": iss,
        "iss_municipio": municipio,
        "total_pct": round(total, 2),
    }


def calcular_tributos_lucro_presumido(municipio: str = "Rio de Janeiro") -> dict:
    """Lucro Presumido (cumulativo)."""
    iss = get_iss(municipio)
    pis = 0.65
    cofins = 3.0
    total = pis + cofins + iss

    return {
        "regime": "lucro_presumido",
        "pis_pct": pis,
        "cofins_pct": cofins,
        "iss_pct": iss,
        "iss_municipio": municipio,
        "total_pct": round(total, 2),
    }


def calcular_tributos_simples(
    faturamento_12m: float,
    municipio: str = "Rio de Janeiro",
) -> dict:
    """Simples Nacional — Anexo IV (limpeza/vigilância).

    ISS já incluso na alíquota do Simples.
    """
    # Faixas Anexo IV (simplificado)
    if faturamento_12m <= 180_000:
        aliquota = 4.5
    elif faturamento_12m <= 360_000:
        aliquota = 9.0
    elif faturamento_12m <= 720_000:
        aliquota = 10.2
    elif faturamento_12m <= 1_800_000:
        aliquota = 14.0
    elif faturamento_12m <= 3_600_000:
        aliquota = 22.0
    else:
        aliquota = 33.0  # Acima do limite

    return {
        "regime": "simples_nacional",
        "aliquota_efetiva_pct": aliquota,
        "nota": "ISS já incluso na alíquota do Simples (Anexo IV)",
        "total_pct": aliquota,
    }


def calcular_tributos(
    regime: str = "lucro_real",
    municipio: str = "Rio de Janeiro",
    **kwargs,
) -> dict:
    """Wrapper que seleciona o regime correto."""
    if regime == "lucro_real":
        return calcular_tributos_lucro_real(municipio, **kwargs)
    elif regime == "lucro_presumido":
        return calcular_tributos_lucro_presumido(municipio)
    elif regime == "simples":
        return calcular_tributos_simples(
            kwargs.get("faturamento_12m", 1_000_000), municipio
        )
    else:
        log.warning(f"Regime '{regime}' não reconhecido, usando lucro_real")
        return calcular_tributos_lucro_real(municipio)
