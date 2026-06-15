"""Broadcast SSE por tenant. Single-process — substitui WebSocket pro MVP."""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

from radar.metrics import RADAR_SSE_CONEXOES

log = logging.getLogger("radar.sse")


class SSEManager:
    """Mantém asyncio.Queue por (tenant_id, conexao). Broadcast push pra todas conexões do tenant."""

    def __init__(self):
        self._filas: dict[int, set[asyncio.Queue]] = defaultdict(set)

    async def subscribe(self, tenant_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._filas[tenant_id].add(q)
        RADAR_SSE_CONEXOES.inc()
        log.info(f"SSE subscribe tenant={tenant_id} conexoes={len(self._filas[tenant_id])}")
        return q

    async def unsubscribe(self, tenant_id: int, q: asyncio.Queue) -> None:
        self._filas[tenant_id].discard(q)
        if not self._filas[tenant_id]:
            del self._filas[tenant_id]
        RADAR_SSE_CONEXOES.dec()

    async def publish(self, tenant_id: int, evento: dict) -> int:
        """Publica pra todas as conexões do tenant. Retorna nº de entregas."""
        filas = list(self._filas.get(tenant_id, set()))
        if not filas:
            return 0
        msg = json.dumps(evento, ensure_ascii=False, default=str)
        entregues = 0
        for q in filas:
            try:
                q.put_nowait(msg)
                entregues += 1
            except asyncio.QueueFull:
                log.warning(f"SSE queue cheia (tenant {tenant_id}), descartando msg")
        return entregues


sse_manager = SSEManager()
