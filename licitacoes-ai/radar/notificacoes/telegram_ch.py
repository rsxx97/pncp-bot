"""Canal Telegram — usa Bot API."""
from __future__ import annotations

import httpx

from radar.eventos.tipos import EventoRadar
from radar.notificacoes.base import NotificationChannel


_ICONES = {
    "urgente": "🚨",
    "alta": "⚠️",
    "normal": "🔔",
}


class TelegramChannel(NotificationChannel):
    canal = "telegram"

    async def enviar(self, evento: EventoRadar, destino: dict) -> dict:
        token = destino.get("bot_token")
        chat = destino.get("chat_id")
        if not token or not chat:
            return {"status": "erro", "erro": "bot_token/chat_id ausentes"}

        icone = _ICONES.get(evento.criticidade.value, "🔔")
        msg = (
            f"{icone} <b>{evento.titulo or evento.tipo.value}</b>\n"
            f"<i>{evento.tipo.value} · {evento.criticidade.value.upper()}</i>\n\n"
            f"{evento.descricao or ''}"
        )
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                )
            if r.status_code == 200 and r.json().get("ok"):
                return {"status": "enviado", "message_id": r.json()["result"]["message_id"]}
            return {"status": "erro", "erro": f"HTTP {r.status_code}: {r.text[:200]}"}
        except httpx.HTTPError as e:
            return {"status": "erro", "erro": str(e)}

    async def testar(self, destino: dict) -> dict:
        token = destino.get("bot_token")
        chat = destino.get("chat_id")
        if not token or not chat:
            return {"status": "erro", "erro": "bot_token/chat_id ausentes"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": "🔔 Teste — Radar de Pregão funcionando ✓"},
            )
        return {"status": "enviado" if r.status_code == 200 else "erro", "http": r.status_code}
