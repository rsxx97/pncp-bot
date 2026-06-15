"""Throttle simples por (tenant, tipo+canal) via SQLite. Default: 10s."""
from __future__ import annotations

from datetime import datetime, timedelta


def deve_throttlar(tenant_id: int, tipo_canal: str, janela_seg: int = 10) -> bool:
    from shared.database import get_db

    conn = get_db()
    row = conn.execute(
        "SELECT ultima_em FROM radar_throttle WHERE tenant_id = ? AND tipo_canal = ?",
        (tenant_id, tipo_canal),
    ).fetchone()

    agora = datetime.now()
    if row:
        try:
            ultima = datetime.fromisoformat(row["ultima_em"])
            if agora - ultima < timedelta(seconds=janela_seg):
                return True
        except ValueError:
            pass

    conn.execute(
        """INSERT INTO radar_throttle (tenant_id, tipo_canal, ultima_em) VALUES (?, ?, ?)
           ON CONFLICT(tenant_id, tipo_canal) DO UPDATE SET ultima_em = excluded.ultima_em""",
        (tenant_id, tipo_canal, agora.isoformat()),
    )
    conn.commit()
    return False
