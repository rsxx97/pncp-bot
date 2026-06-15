"""Canal WhatsApp — interface pronta, plug Z-API ou Twilio depois.

Env: WHATSAPP_PROVIDER=zapi|twilio, ZAPI_INSTANCE_ID, ZAPI_TOKEN, ZAPI_CLIENT_TOKEN
"""
from __future__ import annotations

import os

import httpx

from radar.eventos.tipos import EventoRadar
from radar.notificacoes.base import NotificationChannel


class WhatsAppChannel(NotificationChannel):
    canal = "whatsapp"

    async def enviar(self, evento: EventoRadar, destino: dict) -> dict:
        provider = (destino.get("provider") or os.environ.get("WHATSAPP_PROVIDER", "")).lower()
        numero = destino.get("numero")
        if not numero:
            return {"status": "erro", "erro": "numero ausente"}
        texto = f"*{evento.titulo or evento.tipo.value}*\n_{evento.criticidade.value.upper()}_\n\n{evento.descricao or ''}"
        if provider == "zapi":
            return await _zapi_send(numero, texto)
        return {"status": "erro", "erro": f"provider '{provider}' não suportado ainda (use zapi)"}

    async def testar(self, destino: dict) -> dict:
        provider = (destino.get("provider") or os.environ.get("WHATSAPP_PROVIDER", "")).lower()
        numero = destino.get("numero")
        if not numero:
            return {"status": "erro", "erro": "numero ausente"}
        if provider == "zapi":
            return await _zapi_send(numero, "Teste — Radar de Pregão. Funcionando ✓")
        return {"status": "erro", "erro": f"provider '{provider}' não suportado"}


async def _zapi_send(numero: str, texto: str) -> dict:
    inst = os.environ.get("ZAPI_INSTANCE_ID")
    tok = os.environ.get("ZAPI_TOKEN")
    client_tok = os.environ.get("ZAPI_CLIENT_TOKEN")
    if not (inst and tok and client_tok):
        return {"status": "erro", "erro": "ZAPI_* não configuradas"}
    url = f"https://api.z-api.io/instances/{inst}/token/{tok}/send-text"
    headers = {"Client-Token": client_tok, "Content-Type": "application/json"}
    body = {"phone": numero, "message": texto}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(url, json=body, headers=headers)
        return {"status": "enviado" if r.status_code == 200 else "erro", "http": r.status_code, "body": r.text[:200]}
    except httpx.HTTPError as e:
        return {"status": "erro", "erro": str(e)}
