"""Histórico de eventos + export CSV."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from api.deps import get_connection
from api.routes.auth import require_tenant

router = APIRouter(prefix="/api/radar/historico", tags=["radar-historico"])


def _buscar_eventos(tenant_id: int, dias: int | None, tipo: str | None, pregao_id: int | None, limite: int = 500) -> list[dict]:
    conn = get_connection()
    where = ["e.tenant_id = ?"]
    params: list = [tenant_id]
    if dias:
        cutoff = (datetime.now() - timedelta(days=dias)).isoformat()
        where.append("e.criado_em >= ?")
        params.append(cutoff)
    if tipo:
        where.append("e.tipo = ?")
        params.append(tipo)
    if pregao_id:
        where.append("e.pregao_monitorado_id = ?")
        params.append(pregao_id)
    rows = conn.execute(
        f"""SELECT e.*, p.identificador, p.numero AS pregao_numero, p.orgao AS pregao_orgao, po.slug AS portal_slug
            FROM radar_eventos e
            JOIN radar_pregoes_monitorados p ON p.id = e.pregao_monitorado_id
            JOIN portais po ON po.id = p.portal_id
            WHERE {' AND '.join(where)}
            ORDER BY e.criado_em DESC
            LIMIT ?""",
        params + [limite],
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("payload_json"):
            try:
                d["payload"] = json.loads(d["payload_json"])
            except json.JSONDecodeError:
                d["payload"] = {}
            del d["payload_json"]
        out.append(d)
    return out


@router.get("")
def historico(
    tenant: dict = Depends(require_tenant),
    dias: int = Query(30, ge=1, le=365),
    tipo: str | None = Query(None),
    pregao_id: int | None = Query(None),
    limite: int = Query(200, ge=1, le=1000),
):
    return _buscar_eventos(tenant["id"], dias, tipo, pregao_id, limite)


@router.post("/marcar-lido/{evento_id}")
def marcar_lido(evento_id: int, tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    conn.execute(
        "UPDATE radar_eventos SET lido_em = datetime('now') WHERE id = ? AND tenant_id = ?",
        (evento_id, tenant["id"]),
    )
    conn.commit()
    return {"ok": True}


@router.post("/marcar-todos-lidos")
def marcar_todos_lidos(tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    conn.execute(
        "UPDATE radar_eventos SET lido_em = datetime('now') WHERE tenant_id = ? AND lido_em IS NULL",
        (tenant["id"],),
    )
    conn.commit()
    return {"ok": True}


@router.get("/export.csv")
def export_csv(
    tenant: dict = Depends(require_tenant),
    dias: int = Query(90, ge=1, le=365),
    tipo: str | None = Query(None),
):
    eventos = _buscar_eventos(tenant["id"], dias, tipo, None, limite=10000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "criado_em", "portal", "pregao", "orgao", "tipo", "criticidade", "titulo", "descricao"])
    for e in eventos:
        w.writerow([
            e["id"], e["criado_em"], e["portal_slug"],
            e.get("pregao_numero") or e["identificador"],
            (e.get("pregao_orgao") or "")[:80],
            e["tipo"], e["criticidade"], e["titulo"], (e["descricao"] or "")[:200],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=radar_eventos_{datetime.now():%Y%m%d}.csv"},
    )
