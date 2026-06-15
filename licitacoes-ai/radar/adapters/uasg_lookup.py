"""Resolve UASG -> {CNPJ órgão, nome, UF, município} via dadosabertos.compras.gov.br.

Endpoint: GET /modulo-uasg/1_consultarUasg?codigoUasg=X&statusUasg=true
Doc: https://dadosabertos.compras.gov.br/swagger-ui/index.html#/05%20-%20UASG/consultarUasg

Cache em memória — UASG não muda. TTL longo (24h) é mais que suficiente.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger("radar.uasg_lookup")

URL = "https://dadosabertos.compras.gov.br/modulo-uasg/1_consultarUasg"
CACHE_TTL_SEG = 24 * 3600
_CACHE: dict[str, tuple[dict, float]] = {}


async def consultar_uasg(codigo_uasg: str) -> dict | None:
    """Retorna dict com dados da UASG, ou None se não encontrar / falhar.

    Shape:
      {
        "codigoUasg": "730012",
        "nomeUasg": "BATALHAO NAVAL",
        "siglaUf": "RJ",
        "nomeMunicipioIbge": "RIO DE JANEIRO",
        "codigoMunicipioIbge": 3304557,
        "cnpjCpfOrgao": "00394502000144",
        "cnpjCpfOrgaoVinculado": "03277610000125",
        "cnpjCpfOrgaoSuperior": "00394411000109",
        "codigoOrgao": 52131,
        "statusUasg": true,
        ...
      }
    """
    codigo_uasg = str(codigo_uasg).strip()
    if not codigo_uasg:
        return None

    cached = _CACHE.get(codigo_uasg)
    if cached and (time.monotonic() - cached[1]) < CACHE_TTL_SEG:
        return cached[0]

    params = {"codigoUasg": codigo_uasg, "statusUasg": "true", "pagina": 1}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(URL, params=params, headers={"Accept": "application/json"})
    except httpx.HTTPError as e:
        log.warning(f"consultarUasg({codigo_uasg}) erro de rede: {e}")
        return None
    if r.status_code != 200:
        log.warning(f"consultarUasg({codigo_uasg}) HTTP {r.status_code}: {r.text[:200]}")
        return None
    data = r.json()
    resultado = data.get("resultado") or []
    if not resultado:
        log.info(f"consultarUasg({codigo_uasg}) sem resultado")
        return None
    uasg = resultado[0]
    _CACHE[codigo_uasg] = (uasg, time.monotonic())
    return uasg
