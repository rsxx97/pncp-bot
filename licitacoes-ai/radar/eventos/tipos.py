"""Tipos de evento detectados pelo radar + criticidade."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TipoEvento(str, Enum):
    SESSAO_ABERTA       = "SESSAO_ABERTA"
    SESSAO_SUSPENSA     = "SESSAO_SUSPENSA"
    SESSAO_RETOMADA     = "SESSAO_RETOMADA"
    SESSAO_ENCERRADA    = "SESSAO_ENCERRADA"

    NOVO_LANCE          = "NOVO_LANCE"
    USUARIO_SUPERADO    = "USUARIO_SUPERADO"
    USUARIO_NA_FRENTE   = "USUARIO_NA_FRENTE"

    MENSAGEM_PREGOEIRO  = "MENSAGEM_PREGOEIRO"
    MUDANCA_FASE        = "MUDANCA_FASE"

    CONVOCACAO_PROPOSTA      = "CONVOCACAO_PROPOSTA"
    CONVOCACAO_DOCUMENTACAO  = "CONVOCACAO_DOCUMENTACAO"
    PEDIDO_DILIGENCIA        = "PEDIDO_DILIGENCIA"
    CONTRAPROPOSTA           = "CONTRAPROPOSTA"

    HABILITADO          = "HABILITADO"
    INABILITADO         = "INABILITADO"
    RECURSO_ABERTO      = "RECURSO_ABERTO"
    RECURSO_JULGADO     = "RECURSO_JULGADO"

    ADJUDICADO          = "ADJUDICADO"
    HOMOLOGADO          = "HOMOLOGADO"
    FRACASSADO          = "FRACASSADO"
    DESERTO             = "DESERTO"

    REPUBLICACAO        = "REPUBLICACAO"
    ADIAMENTO           = "ADIAMENTO"
    CANCELAMENTO        = "CANCELAMENTO"


class Criticidade(str, Enum):
    NORMAL  = "normal"
    ALTA    = "alta"
    URGENTE = "urgente"


CRITICIDADE_PADRAO: dict[TipoEvento, Criticidade] = {
    TipoEvento.USUARIO_SUPERADO:       Criticidade.URGENTE,
    TipoEvento.CONVOCACAO_PROPOSTA:    Criticidade.URGENTE,
    TipoEvento.CONVOCACAO_DOCUMENTACAO: Criticidade.URGENTE,
    TipoEvento.PEDIDO_DILIGENCIA:      Criticidade.URGENTE,
    TipoEvento.CONTRAPROPOSTA:         Criticidade.URGENTE,
    TipoEvento.MENSAGEM_PREGOEIRO:     Criticidade.ALTA,
    TipoEvento.MUDANCA_FASE:           Criticidade.ALTA,
    TipoEvento.SESSAO_SUSPENSA:        Criticidade.ALTA,
    TipoEvento.INABILITADO:            Criticidade.ALTA,
    TipoEvento.RECURSO_ABERTO:         Criticidade.ALTA,
    TipoEvento.RECURSO_JULGADO:        Criticidade.ALTA,
    TipoEvento.CANCELAMENTO:           Criticidade.ALTA,
    TipoEvento.HOMOLOGADO:             Criticidade.ALTA,
    TipoEvento.ADJUDICADO:             Criticidade.ALTA,
    TipoEvento.FRACASSADO:             Criticidade.ALTA,
    TipoEvento.USUARIO_NA_FRENTE:      Criticidade.ALTA,
}


@dataclass
class EventoRadar:
    tipo: TipoEvento
    tenant_id: int
    pregao_monitorado_id: int
    criticidade: Criticidade = Criticidade.NORMAL
    titulo: str = ""
    descricao: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    criado_em: datetime = field(default_factory=datetime.now)
    id: int | None = None  # preenchido após persistir

    @classmethod
    def criar(cls, tipo: TipoEvento, **kwargs):
        return cls(tipo=tipo, criticidade=CRITICIDADE_PADRAO.get(tipo, Criticidade.NORMAL), **kwargs)

    def to_json_payload(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo.value,
            "criticidade": self.criticidade.value,
            "tenant_id": self.tenant_id,
            "pregao_monitorado_id": self.pregao_monitorado_id,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "payload": self.payload,
            "criado_em": self.criado_em.isoformat(),
        }
