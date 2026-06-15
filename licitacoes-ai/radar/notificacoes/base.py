"""Contrato dos canais de notificação."""
from __future__ import annotations

from abc import ABC, abstractmethod

from radar.eventos.tipos import EventoRadar


class NotificationChannel(ABC):
    canal: str = ""

    @abstractmethod
    async def enviar(self, evento: EventoRadar, destino: dict) -> dict:
        """Retorna {status: 'enviado'|'throttled'|'erro', message_id?, erro?}.

        `destino` contém o necessário pro canal:
          in_app:    {tenant_id}
          web_push:  {endpoint, p256dh, auth}
          email:     {to}
          telegram:  {bot_token, chat_id}
          whatsapp:  {numero, provider}
        """

    @abstractmethod
    async def testar(self, destino: dict) -> dict:
        ...
