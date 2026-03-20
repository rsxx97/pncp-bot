"""Rotas de métricas do dashboard."""
from datetime import datetime, date
from fastapi import APIRouter

from api.deps import get_connection

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/metrics")
def get_metrics():
    conn = get_connection()
    hoje = date.today().isoformat()

    # Editais hoje
    row = conn.execute(
        "SELECT COUNT(*) as total FROM editais WHERE DATE(created_at) = ?", (hoje,)
    ).fetchone()
    editais_hoje = row["total"]

    # Score 60+
    row = conn.execute(
        "SELECT COUNT(*) as total FROM editais WHERE score_relevancia >= 60"
    ).fetchone()
    editais_score_60 = row["total"]

    # Planilhas prontas
    row = conn.execute(
        "SELECT COUNT(*) as total FROM editais WHERE planilha_path IS NOT NULL"
    ).fetchone()
    planilhas_prontas = row["total"]

    # Volume total das planilhas prontas
    row = conn.execute(
        "SELECT COALESCE(SUM(valor_proposta), 0) as total FROM editais WHERE planilha_path IS NOT NULL"
    ).fetchone()
    volume_total = row["total"]

    # Custo API hoje
    row = conn.execute(
        "SELECT COALESCE(SUM(custo_estimado), 0) as total, COUNT(*) as chamadas "
        "FROM execucoes WHERE DATE(created_at) = ?", (hoje,)
    ).fetchone()
    custo_api_hoje = row["total"]
    chamadas_hoje = row["chamadas"]

    # Monitor state
    monitor = conn.execute("SELECT * FROM monitor_state WHERE id = 1").fetchone()

    return {
        "editais_hoje": editais_hoje,
        "editais_score_60": editais_score_60,
        "planilhas_prontas": planilhas_prontas,
        "volume_total": volume_total,
        "custo_api_hoje_usd": round(custo_api_hoje, 4),
        "chamadas_api_hoje": chamadas_hoje,
        "ultimo_scan": monitor["ultima_consulta"] if monitor else None,
        "monitor_ativo": bool(monitor["ativo"]) if monitor else False,
    }


@router.get("/weekly-chart")
def get_weekly_chart():
    conn = get_connection()

    rows = conn.execute("""
        SELECT
            strftime('%W', created_at) as semana,
            strftime('%d', MIN(created_at)) || ' ' ||
            CASE strftime('%m', MIN(created_at))
                WHEN '01' THEN 'jan' WHEN '02' THEN 'fev' WHEN '03' THEN 'mar'
                WHEN '04' THEN 'abr' WHEN '05' THEN 'mai' WHEN '06' THEN 'jun'
                WHEN '07' THEN 'jul' WHEN '08' THEN 'ago' WHEN '09' THEN 'set'
                WHEN '10' THEN 'out' WHEN '11' THEN 'nov' WHEN '12' THEN 'dez'
            END as week,
            SUM(CASE WHEN score_relevancia >= 60 THEN 1 ELSE 0 END) as score60,
            SUM(CASE WHEN score_relevancia < 60 OR score_relevancia IS NULL THEN 1 ELSE 0 END) as abaixo
        FROM editais
        WHERE created_at >= datetime('now', '-28 days')
        GROUP BY strftime('%W', created_at)
        ORDER BY semana ASC
    """).fetchall()

    return [dict(r) for r in rows]
