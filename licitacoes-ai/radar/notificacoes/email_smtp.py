"""Canal Email via SMTP genérico (SES, Mailgun, SendGrid, Gmail relay, etc).

Env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TLS=true|false
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

from radar.eventos.tipos import EventoRadar
from radar.notificacoes.base import NotificationChannel


class EmailChannel(NotificationChannel):
    canal = "email"

    async def enviar(self, evento: EventoRadar, destino: dict) -> dict:
        to = destino.get("to")
        if not to:
            return {"status": "erro", "erro": "destinatário ausente"}

        msg = EmailMessage()
        msg["Subject"] = f"[Radar Pregão] {evento.tipo.value} — {evento.titulo or ''}"[:120]
        msg["From"] = os.environ.get("SMTP_FROM", "no-reply@licitacoes-ai")
        msg["To"] = to
        msg.set_content(
            f"Evento: {evento.tipo.value}\n"
            f"Criticidade: {evento.criticidade.value}\n"
            f"Título: {evento.titulo}\n\n"
            f"{evento.descricao}\n\n"
            f"Pregão monitorado: #{evento.pregao_monitorado_id}\n"
            f"Em: {evento.criado_em.isoformat()}\n"
        )

        return await _send(msg, to)

    async def testar(self, destino: dict) -> dict:
        to = destino.get("to")
        if not to:
            return {"status": "erro", "erro": "destinatário ausente"}
        msg = EmailMessage()
        msg["Subject"] = "[Radar Pregão] Teste de notificação por e-mail"
        msg["From"] = os.environ.get("SMTP_FROM", "no-reply@licitacoes-ai")
        msg["To"] = to
        msg.set_content("Teste do canal de e-mail. Se chegou, está funcionando.")
        return await _send(msg, to)


async def _send(msg: EmailMessage, to: str) -> dict:
    host = os.environ.get("SMTP_HOST")
    if not host:
        return {"status": "erro", "erro": "SMTP_HOST não configurado"}
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    use_tls = os.environ.get("SMTP_TLS", "true").lower() == "true"

    try:
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
                if user:
                    s.login(user, pwd or "")
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                if use_tls:
                    s.starttls(context=ssl.create_default_context())
                if user:
                    s.login(user, pwd or "")
                s.send_message(msg)
        return {"status": "enviado", "destino": to}
    except Exception as e:
        return {"status": "erro", "erro": str(e)}
