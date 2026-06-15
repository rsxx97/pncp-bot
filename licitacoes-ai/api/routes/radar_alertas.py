"""Matriz tipo_evento × canal + teste de canal."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_connection
from api.routes.auth import require_tenant
from radar.eventos.tipos import TipoEvento
from radar.notificacoes.registry import CHANNELS

router = APIRouter(prefix="/api/radar/alertas", tags=["radar-alertas"])


CANAIS = list(CHANNELS.keys())


@router.get("")
def listar_config(tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT tipo_evento, canal, ativo, regras_json FROM radar_alertas_config WHERE tenant_id = ?",
        (tenant["id"],),
    ).fetchall()
    matriz: dict[str, dict[str, dict]] = {t.value: {c: {"ativo": False, "regras": {}} for c in CANAIS} for t in TipoEvento}
    for r in rows:
        if r["tipo_evento"] in matriz and r["canal"] in matriz[r["tipo_evento"]]:
            matriz[r["tipo_evento"]][r["canal"]] = {
                "ativo": bool(r["ativo"]),
                "regras": json.loads(r["regras_json"] or "{}"),
            }
    return {
        "tipos": [t.value for t in TipoEvento],
        "canais": CANAIS,
        "matriz": matriz,
    }


class ConfigUpdate(BaseModel):
    tipo_evento: str
    canal: str
    ativo: bool
    regras: dict | None = None


@router.put("")
def upsert_config(body: ConfigUpdate, tenant: dict = Depends(require_tenant)):
    if body.canal not in CANAIS:
        raise HTTPException(400, f"Canal inválido. Use um de: {CANAIS}")
    conn = get_connection()
    conn.execute(
        """INSERT INTO radar_alertas_config (tenant_id, tipo_evento, canal, ativo, regras_json)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(tenant_id, tipo_evento, canal) DO UPDATE SET
             ativo = excluded.ativo,
             regras_json = excluded.regras_json""",
        (
            tenant["id"], body.tipo_evento, body.canal,
            1 if body.ativo else 0,
            json.dumps(body.regras or {}, ensure_ascii=False),
        ),
    )
    conn.commit()
    return {"ok": True}


class TestarCanalIn(BaseModel):
    canal: str
    destino: dict


@router.post("/testar")
async def testar_canal(body: TestarCanalIn, tenant: dict = Depends(require_tenant)):
    ch = CHANNELS.get(body.canal)
    if not ch:
        raise HTTPException(400, f"Canal '{body.canal}' não existe")
    destino = dict(body.destino)
    destino.setdefault("tenant_id", tenant["id"])
    return await ch.testar(destino)


# ── Web Push subscriptions ─────────────────────────────────────────────

class WebPushSub(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None = None


@router.post("/web-push/subscribe")
def subscribe_push(body: WebPushSub, tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    conn.execute(
        """INSERT INTO radar_web_push_subs (tenant_id, endpoint, p256dh, auth, user_agent)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(endpoint) DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth""",
        (tenant["id"], body.endpoint, body.p256dh, body.auth, body.user_agent),
    )
    conn.commit()
    return {"ok": True}


@router.delete("/web-push/subscribe")
def unsubscribe_push(endpoint: str, tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    conn.execute(
        "DELETE FROM radar_web_push_subs WHERE tenant_id = ? AND endpoint = ?",
        (tenant["id"], endpoint),
    )
    conn.commit()
    return {"ok": True}
