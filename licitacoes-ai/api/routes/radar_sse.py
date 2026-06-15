"""SSE: stream de eventos por tenant. Auth via query ?token=... (EventSource não envia headers)."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from api.routes.auth import _decodificar_token
from radar.sse_manager import sse_manager
from shared.database import get_tenant

router = APIRouter(prefix="/api/radar", tags=["radar-sse"])


@router.get("/stream")
async def stream(token: str = Query(...)):
    payload = _decodificar_token(token)
    if not payload:
        raise HTTPException(401, "Token inválido")
    tenant_id = int(payload["sub"])
    tenant = get_tenant(tenant_id)
    if not tenant or not tenant.get("ativo"):
        raise HTTPException(403, "Conta desativada")

    q: asyncio.Queue = await sse_manager.subscribe(tenant_id)

    async def gen():
        try:
            yield {"event": "hello", "data": json.dumps({"tenant_id": tenant_id, "msg": "Conectado ao Radar"})}
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=30)
                    yield {"event": "radar", "data": msg}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "."}
        finally:
            await sse_manager.unsubscribe(tenant_id, q)

    return EventSourceResponse(gen())
