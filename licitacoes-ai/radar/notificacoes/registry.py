"""Registry de canais de notificação + dispatcher central."""
from __future__ import annotations

import json
import logging

from radar.eventos.tipos import EventoRadar
from radar.metrics import RADAR_NOTIF_TOTAL
from radar.notificacoes.base import NotificationChannel
from radar.notificacoes.email_smtp import EmailChannel
from radar.notificacoes.in_app import InAppChannel
from radar.notificacoes.telegram_ch import TelegramChannel
from radar.notificacoes.throttle import deve_throttlar
from radar.notificacoes.web_push import WebPushChannel
from radar.notificacoes.whatsapp import WhatsAppChannel

log = logging.getLogger("radar.notif")

CHANNELS: dict[str, NotificationChannel] = {
    "in_app": InAppChannel(),
    "telegram": TelegramChannel(),
    "email": EmailChannel(),
    "web_push": WebPushChannel(),
    "whatsapp": WhatsAppChannel(),
}


async def disparar_evento(evento: EventoRadar) -> list[dict]:
    """Lê alertas_config do tenant, expande pra cada canal habilitado, dispara, loga."""
    from shared.database import get_db

    conn = get_db()
    rows = conn.execute(
        """SELECT canal, regras_json FROM radar_alertas_config
           WHERE tenant_id = ? AND tipo_evento = ? AND ativo = 1""",
        (evento.tenant_id, evento.tipo.value),
    ).fetchall()

    if not rows:
        return [{"status": "sem_canal_configurado"}]

    resultados = []
    for row in rows:
        canal = row["canal"]
        regras = json.loads(row["regras_json"] or "{}")
        if not _passa_regras(evento, regras):
            continue
        if deve_throttlar(evento.tenant_id, f"{evento.tipo.value}:{canal}"):
            _log_notif(evento, canal, "throttled", None)
            resultados.append({"canal": canal, "status": "throttled"})
            continue

        destino = _resolver_destino(canal, evento.tenant_id, regras)
        ch = CHANNELS.get(canal)
        if not ch:
            resultados.append({"canal": canal, "status": "erro", "erro": "canal desconhecido"})
            continue
        r = await ch.enviar(evento, destino)
        RADAR_NOTIF_TOTAL.labels(canal=canal, status=r.get("status", "erro")).inc()
        _log_notif(evento, canal, r.get("status", "erro"), r.get("erro"))
        resultados.append({"canal": canal, **r})
    return resultados


def _passa_regras(evento: EventoRadar, regras: dict) -> bool:
    if not regras:
        return True
    valor_min = regras.get("valor_min")
    if valor_min:
        v = (evento.payload.get("snapshot") or {}).get("valor_estimado") or evento.payload.get("valor") or 0
        if (v or 0) < valor_min:
            return False
    portal = regras.get("portal")
    if portal:
        snap_portal = (evento.payload.get("snapshot") or {}).get("portal_slug")
        if snap_portal and snap_portal != portal:
            return False
    return True


def _resolver_destino(canal: str, tenant_id: int, regras: dict) -> dict:
    """Default: usa env/credenciais. Pode ser sobrescrito por regras."""
    import os
    if canal == "in_app":
        return {"tenant_id": tenant_id}
    if canal == "telegram":
        return {
            "bot_token": regras.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN"),
            "chat_id": regras.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID"),
        }
    if canal == "email":
        return {"to": regras.get("to")}
    if canal == "web_push":
        from shared.database import get_db
        rows = get_db().execute(
            "SELECT endpoint, p256dh, auth FROM radar_web_push_subs WHERE tenant_id = ?", (tenant_id,)
        ).fetchall()
        return {"subscriptions": [dict(r) for r in rows]}
    if canal == "whatsapp":
        return {"numero": regras.get("numero"), "provider": regras.get("provider")}
    return {}


def _log_notif(evento: EventoRadar, canal: str, status: str, erro: str | None):
    from shared.database import get_db
    if not evento.id:
        return
    get_db().execute(
        """INSERT INTO radar_notificacoes_log (tenant_id, evento_id, canal, status, erro)
           VALUES (?, ?, ?, ?, ?)""",
        (evento.tenant_id, evento.id, canal, status, erro),
    )
    get_db().commit()
