"""Notificação in-app: broadcast SSE pra todas as conexões do tenant."""
from __future__ import annotations

from radar.eventos.tipos import EventoRadar
from radar.notificacoes.base import NotificationChannel
from radar.sse_manager import sse_manager


class InAppChannel(NotificationChannel):
    canal = "in_app"

    async def enviar(self, evento: EventoRadar, destino: dict) -> dict:
        tid = destino.get("tenant_id") or evento.tenant_id
        entregues = await sse_manager.publish(tid, {"evento": evento.to_json_payload()})
        return {"status": "enviado", "entregas_sse": entregues}

    async def testar(self, destino: dict) -> dict:
        tid = destino.get("tenant_id")
        if not tid:
            return {"status": "erro", "erro": "tenant_id ausente"}
        await sse_manager.publish(tid, {"teste": True, "mensagem": "Notificação de teste — funciona ✓"})
        return {"status": "enviado"}
