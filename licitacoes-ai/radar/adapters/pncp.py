"""Adapter PNCP — API oficial. Sem autenticação (consulta pública).

Identificador esperado: "CNPJ-ANO-SEQ" (ex: 03589068000146-2026-40).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from radar.adapters.base import (
    NotFoundError,
    PortalAdapter,
    PregaoSnapshot,
    RateLimitError,
)

log = logging.getLogger("radar.pncp")

BASE = "https://pncp.gov.br/api/consulta/v1"
PNCP_APP_BASE = "https://pncp.gov.br/app/editais"

# situacaoCompraId conhecidos no PNCP:
#   1 = Divulgada no PNCP (default — não informa fase concreta)
#   2 = Revogada
#   3 = Anulada
#   4 = Suspensa
_SITUACAO_TERMINAL = {2, 3}   # encerra o pregão
_SITUACAO_SUSPENSO = {4}

# Modalidades que tem fase de "lances" (pregão eletrônico/presencial, dispensa
# eletrônica, RDC eletrônico).
_MODALIDADES_PREGAO = {4, 5, 6, 7, 8}


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _classificar_status(data: dict, agora: datetime) -> tuple[str, str | None]:
    """Retorna (status, fase). Inferência por datas + flags do PNCP."""
    situacao_id = data.get("situacaoCompraId")
    contratacao_excluida = data.get("contratacaoExcluida")
    existe_resultado = bool(data.get("existeResultado"))
    valor_homologado = data.get("valorTotalHomologado")
    abertura = _parse_dt(data.get("dataAberturaProposta") or data.get("dataAberturaPropostaPncp"))
    encerramento = _parse_dt(data.get("dataEncerramentoProposta") or data.get("dataEncerramentoPropostaPncp"))
    modalidade_id = data.get("modalidadeId") or data.get("codigoModalidade") or 0

    if contratacao_excluida or situacao_id in _SITUACAO_TERMINAL:
        return "encerrado", None

    if situacao_id in _SITUACAO_SUSPENSO:
        return "suspenso", None

    if valor_homologado is not None:
        return "encerrado", "homologacao"

    if encerramento and agora > encerramento + timedelta(hours=12):
        # Passou encerramento de propostas + 12h — provavelmente em habilitação/homologação
        if existe_resultado:
            return "encerrado", "homologacao"
        return "em_sessao", "habilitacao"

    if encerramento and agora > encerramento:
        # Recém-encerrado — pode estar abrindo sessão de disputa ou em habilitação
        return "em_sessao", "habilitacao" if not existe_resultado else "homologacao"

    if abertura and agora >= abertura:
        # Propostas em curso (ou sessão de lances iniciada)
        fase = "lances" if modalidade_id in _MODALIDADES_PREGAO else "propostas"
        return "em_sessao", fase

    return "agendado", None


class PncpAdapter(PortalAdapter):
    slug = "pncp"
    nome = "PNCP"
    requer_credencial = False
    suporta_lances_proprios = False  # API pública não distingue "meu" CNPJ

    async def fetch_pregao(self, identificador: str) -> PregaoSnapshot:
        parts = identificador.split("-")
        if len(parts) < 3:
            raise NotFoundError(f"identificador inválido: {identificador} (esperado CNPJ-ANO-SEQ)")
        cnpj, ano, seq = parts[0], parts[1], parts[2]
        url = f"{BASE}/orgaos/{cnpj}/compras/{ano}/{seq}"

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.get(url)
            except httpx.HTTPError as e:
                raise RateLimitError(f"erro de rede no PNCP: {e}", retry_em=15) from e

            if r.status_code == 404:
                raise NotFoundError(f"pregão {identificador} não encontrado no PNCP")
            if r.status_code == 429:
                raise RateLimitError("PNCP retornou 429", retry_em=60)
            if r.status_code >= 500:
                raise RateLimitError(f"PNCP HTTP {r.status_code}", retry_em=30)
            r.raise_for_status()
            data = r.json() if r.text else {}

        return self._parse(identificador, data, datetime.now())

    def _parse(self, identificador: str, data: dict[str, Any], agora: datetime) -> PregaoSnapshot:
        status, fase = _classificar_status(data, agora)

        return PregaoSnapshot(
            portal_slug=self.slug,
            identificador=identificador,
            numero=str(data.get("numeroCompra") or data.get("numeroControlePNCP") or ""),
            orgao=(data.get("orgaoEntidade") or {}).get("razaoSocial") or data.get("orgaoNome"),
            objeto=data.get("objetoCompra") or data.get("objeto"),
            data_abertura=_parse_dt(data.get("dataAberturaProposta")),
            data_encerramento=_parse_dt(data.get("dataEncerramentoProposta")),
            status=status,
            fase=fase,
            valor_estimado=data.get("valorTotalEstimado") or data.get("valorEstimado"),
            raw=data,
        )
