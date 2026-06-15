"""Canal Web Push (VAPID). Stub funcional — depende de pywebpush.

Env vars: VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIM_EMAIL
Gere par com: `python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); v.save_key('vapid_priv.pem'); print(v.public_key_b64)"`
"""
from __future__ import annotations

import json
import logging
import os

from radar.eventos.tipos import EventoRadar
from radar.notificacoes.base import NotificationChannel

log = logging.getLogger("radar.webpush")


class WebPushChannel(NotificationChannel):
    canal = "web_push"

    async def enviar(self, evento: EventoRadar, destino: dict) -> dict:
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            return {"status": "erro", "erro": "pywebpush não instalado"}

        priv = os.environ.get("VAPID_PRIVATE_KEY")
        email = os.environ.get("VAPID_CLAIM_EMAIL", "mailto:admin@licitacoes-ai")
        if not priv:
            return {"status": "erro", "erro": "VAPID_PRIVATE_KEY não configurada"}

        subscription = {
            "endpoint": destino.get("endpoint"),
            "keys": {"p256dh": destino.get("p256dh"), "auth": destino.get("auth")},
        }
        payload = {
            "title": f"{evento.tipo.value}",
            "body": (evento.titulo + " — " + evento.descricao)[:200],
            "tag": str(evento.pregao_monitorado_id),
            "criticidade": evento.criticidade.value,
        }
        try:
            webpush(
                subscription_info=subscription,
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=priv,
                vapid_claims={"sub": email},
            )
            return {"status": "enviado"}
        except WebPushException as e:
            return {"status": "erro", "erro": str(e)}

    async def testar(self, destino: dict) -> dict:
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            return {"status": "erro", "erro": "pywebpush não instalado"}
        priv = os.environ.get("VAPID_PRIVATE_KEY")
        if not priv:
            return {"status": "erro", "erro": "VAPID_PRIVATE_KEY não configurada"}
        try:
            webpush(
                subscription_info={
                    "endpoint": destino.get("endpoint"),
                    "keys": {"p256dh": destino.get("p256dh"), "auth": destino.get("auth")},
                },
                data=json.dumps({"title": "Teste", "body": "Web Push funcionando"}),
                vapid_private_key=priv,
                vapid_claims={"sub": os.environ.get("VAPID_CLAIM_EMAIL", "mailto:admin@licitacoes-ai")},
            )
            return {"status": "enviado"}
        except WebPushException as e:
            return {"status": "erro", "erro": str(e)}
