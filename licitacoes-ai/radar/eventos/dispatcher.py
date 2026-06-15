"""Dispatcher: persiste eventos, publica via SSE, dispara notificações por canal."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

from radar.eventos.tipos import EventoRadar
from radar.metrics import RADAR_EVENTOS_TOTAL

log = logging.getLogger("radar.dispatcher")

Handler = Callable[[EventoRadar], Awaitable[None]]


class EventDispatcher:
    """Persiste + dispara handlers em paralelo. 1 falha não derruba os outros."""

    def __init__(self):
        self._handlers: dict[str, list[Handler]] = {}

    def on(self, tipo: str | list[str], handler: Handler) -> None:
        tipos = tipo if isinstance(tipo, list) else [tipo]
        for t in tipos:
            self._handlers.setdefault(t, []).append(handler)

    async def emit(self, evento: EventoRadar, portal_slug: str = "?") -> None:
        evento.id = _persistir_evento(evento)
        RADAR_EVENTOS_TOTAL.labels(portal=portal_slug, tipo=evento.tipo.value, criticidade=evento.criticidade.value).inc()

        handlers = self._handlers.get(evento.tipo.value, []) + self._handlers.get("*", [])
        if not handlers:
            return
        await asyncio.gather(*(_safe(h, evento) for h in handlers), return_exceptions=False)


async def _safe(h: Handler, evento: EventoRadar) -> None:
    try:
        await h(evento)
    except Exception as e:
        log.exception(f"handler {h.__name__} falhou em {evento.tipo.value}: {e}")


def _persistir_evento(evento: EventoRadar) -> int:
    from shared.database import get_db

    conn = get_db()
    cur = conn.execute(
        """INSERT INTO radar_eventos
           (tenant_id, pregao_monitorado_id, tipo, criticidade, titulo, descricao, payload_json, criado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            evento.tenant_id,
            evento.pregao_monitorado_id,
            evento.tipo.value,
            evento.criticidade.value,
            evento.titulo,
            evento.descricao,
            json.dumps(evento.payload, ensure_ascii=False, default=str),
        ),
    )
    conn.commit()
    return cur.lastrowid


dispatcher = EventDispatcher()
