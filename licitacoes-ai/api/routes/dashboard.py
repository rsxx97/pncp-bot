"""Rotas de métricas do dashboard — design premium."""
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Query

from api.deps import get_connection

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _period_filter(period: str) -> str:
    """Retorna cláusula SQL de filtro por período."""
    mapping = {"7d": 7, "30d": 30, "90d": 90, "ytd": None}
    days = mapping.get(period)
    if days:
        return f"AND created_at >= datetime('now', '-{days} days')"
    if period == "ytd":
        year = date.today().year
        return f"AND created_at >= '{year}-01-01'"
    return ""


def _is_monitor_active(monitor) -> bool:
    if not monitor:
        return False
    try:
        ativo = monitor["ativo"]
        if not ativo:
            return False
        ultimo = monitor["ultima_consulta"]
        if not ultimo:
            return False
        dt = datetime.fromisoformat(ultimo.replace("Z", "+00:00")) if "T" in ultimo else datetime.strptime(ultimo, "%Y-%m-%d")
        return (datetime.now() - dt).total_seconds() < 86400
    except Exception:
        return False


@router.get("/metrics")
def get_metrics(period: str = Query("90d")):
    conn = get_connection()
    pf = _period_filter(period)
    hoje = date.today().isoformat()

    total = conn.execute(f"SELECT COUNT(*) as c FROM editais WHERE 1=1 {pf}").fetchone()["c"]
    score60 = conn.execute(f"SELECT COUNT(*) as c FROM editais WHERE score_relevancia >= 60 {pf}").fetchone()["c"]
    planilhas = conn.execute(f"SELECT COUNT(*) as c FROM editais WHERE planilha_path IS NOT NULL {pf}").fetchone()["c"]
    volume = conn.execute(f"SELECT COALESCE(SUM(valor_estimado),0) as c FROM editais WHERE status != 'arquivado' {pf}").fetchone()["c"]

    go_count = conn.execute(f"SELECT COUNT(*) as c FROM editais WHERE parecer LIKE 'go%' {pf}").fetchone()["c"]
    taxa_go = round(go_count / total * 100, 1) if total > 0 else 0

    custo_row = conn.execute(
        "SELECT COALESCE(SUM(custo_estimado),0) as total, COUNT(*) as chamadas FROM execucoes WHERE DATE(created_at) = ?", (hoje,)
    ).fetchone()

    monitor = conn.execute("SELECT * FROM monitor_state WHERE id = 1").fetchone()

    # Faturamento dos pregões vencidos
    try:
        fat_row = conn.execute("SELECT COALESCE(SUM(lance_final), 0) as total, COUNT(*) as qtd FROM pregoes WHERE resultado = 'vencedor'").fetchone()
        faturamento_total = fat_row["total"]
        pregoes_vencidos = fat_row["qtd"]
    except Exception:
        faturamento_total = 0
        pregoes_vencidos = 0

    return {
        "editais_total": total,
        "editais_score_60": score60,
        "planilhas_prontas": planilhas,
        "volume_total": volume,
        "taxa_go": taxa_go,
        "custo_api_hoje_usd": round(custo_row["total"], 4),
        "chamadas_api_hoje": custo_row["chamadas"],
        "ultimo_scan": monitor["ultima_consulta"] if monitor else None,
        "monitor_ativo": _is_monitor_active(monitor),
        "faturamento_total": faturamento_total,
        "pregoes_vencidos": pregoes_vencidos,
    }


@router.get("/funnel")
def get_funnel(period: str = Query("90d")):
    conn = get_connection()
    pf = _period_filter(period)
    def cnt(where): return conn.execute(f"SELECT COUNT(*) as c FROM editais WHERE {where} {pf}").fetchone()["c"]

    monitorados = cnt("1=1")
    score_60 = cnt("score_relevancia >= 60")
    analisados = cnt("status NOT IN ('novo','classificado','analisando','arquivado','erro_analise')")
    go = cnt("parecer LIKE 'go%'")
    planilha = cnt("planilha_path IS NOT NULL")
    participou = cnt("status = 'participou'")
    venceu = cnt("status = 'venceu'")

    return {
        "monitorados": monitorados,
        "score_60_plus": score_60,
        "analisados": analisados,
        "go": go,
        "planilha_pronta": planilha,
        "participou": participou,
        "venceu": venceu,
    }


@router.get("/volume-by-status")
def get_volume_by_status(period: str = Query("90d")):
    conn = get_connection()
    pf = _period_filter(period)
    rows = conn.execute(f"""
        SELECT status, COALESCE(SUM(valor_estimado),0) as vol
        FROM editais WHERE 1=1 {pf}
        GROUP BY status
    """).fetchall()

    result = {}
    total = 0
    count = 0
    for r in rows:
        result[r["status"]] = r["vol"]
        total += r["vol"]
        count += 1

    result["total"] = total
    result["ticket_medio"] = round(total / count, 2) if count > 0 else 0
    return result


@router.get("/alerts")
def get_alerts():
    conn = get_connection()
    now = datetime.now()
    rows = conn.execute("""
        SELECT pncp_id, orgao_nome, objeto, data_abertura, status, planilha_path
        FROM editais
        WHERE data_abertura IS NOT NULL AND status NOT IN ('arquivado','venceu','participou')
        ORDER BY data_abertura ASC
        LIMIT 20
    """).fetchall()

    alerts = []
    for r in rows:
        try:
            da = r["data_abertura"]
            if "T" in da:
                dt = datetime.fromisoformat(da)
            else:
                dt = datetime.strptime(da, "%Y-%m-%d")
            horas = max(0, (dt - now).total_seconds() / 3600)
        except Exception:
            horas = 999

        if horas < 48:
            urgencia = "critico"
        elif horas < 168:
            urgencia = "atencao"
        else:
            urgencia = "ok"

        alerts.append({
            "pncp_id": r["pncp_id"],
            "orgao_nome": r["orgao_nome"],
            "objeto_resumido": (r["objeto"] or "")[:50],
            "data_abertura": r["data_abertura"],
            "horas_restantes": round(horas, 1),
            "status": r["status"],
            "tem_planilha": r["planilha_path"] is not None,
            "urgencia": urgencia,
        })
    return alerts


@router.get("/sparkline/{metric}")
def get_sparkline(metric: str, days: int = Query(14)):
    conn = get_connection()
    result = []
    for i in range(days - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        if metric == "editais":
            v = conn.execute("SELECT COUNT(*) as c FROM editais WHERE DATE(created_at) = ?", (d,)).fetchone()["c"]
        elif metric == "pipeline_valor":
            v = conn.execute("SELECT COALESCE(SUM(valor_estimado),0) as c FROM editais WHERE DATE(created_at) <= ? AND status != 'arquivado'", (d,)).fetchone()["c"]
        elif metric == "score_medio":
            v = conn.execute("SELECT COALESCE(AVG(score_relevancia),0) as c FROM editais WHERE DATE(created_at) = ?", (d,)).fetchone()["c"]
        elif metric == "custo_api":
            v = conn.execute("SELECT COALESCE(SUM(custo_estimado),0) as c FROM execucoes WHERE DATE(created_at) = ?", (d,)).fetchone()["c"]
        else:
            v = 0
        result.append(round(v, 2) if isinstance(v, float) else v)
    return result


@router.get("/competitors-ranking")
def get_competitors_ranking():
    import json
    from pathlib import Path
    config_path = Path(__file__).parent.parent.parent / "config" / "concorrentes.json"
    if not config_path.exists():
        return []
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)

    ranking = []
    for c in data.get("concorrentes", []):
        nome = c.get("nome_fantasia") or c.get("razao_social") or c.get("nome", "?")
        desc_medio = c.get("desconto_medio", 15)
        lances = c.get("lances_mes", 3)
        taxa = c.get("taxa_vitoria", 0.2)
        score = round((desc_medio * 0.4 + min(lances / 10, 1) * 30 + taxa * 30), 1)
        nivel = "alta" if score > 7 else "media" if score > 4 else "baixa"
        ranking.append({
            "nome": nome,
            "desconto_medio": desc_medio,
            "lances_mes": lances,
            "taxa_vitoria": taxa,
            "score_agressividade": score,
            "nivel": nivel,
        })
    ranking.sort(key=lambda x: x["score_agressividade"], reverse=True)
    return ranking


@router.get("/heatmap")
def get_heatmap():
    import json
    from pathlib import Path
    config_path = Path(__file__).parent.parent.parent / "config" / "concorrentes.json"
    if not config_path.exists():
        return {"segmentos": [], "concorrentes": [], "valores": []}
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)

    segmentos = data.get("segmentos", ["Limpeza", "Apoio adm.", "Vigilância", "Facilities"])
    concorrentes = [c.get("nome_fantasia") or c.get("razao_social") or c.get("nome", "?") for c in data.get("concorrentes", [])]
    valores = []
    for c in data.get("concorrentes", []):
        row = []
        descontos = c.get("descontos_por_segmento", {})
        for s in segmentos:
            row.append(descontos.get(s))
        valores.append(row)
    return {"segmentos": segmentos, "concorrentes": concorrentes, "valores": valores}


@router.get("/calendar")
def get_calendar(month: str = Query(None)):
    conn = get_connection()
    if not month:
        month = date.today().strftime("%Y-%m")

    rows = conn.execute("""
        SELECT pncp_id, orgao_nome, valor_estimado, data_abertura, status
        FROM editais
        WHERE data_abertura IS NOT NULL AND data_abertura LIKE ?
        ORDER BY data_abertura
    """, (f"{month}%",)).fetchall()

    days = {}
    now = datetime.now()
    for r in rows:
        try:
            da = r["data_abertura"]
            d = da[:10]
        except Exception:
            continue
        if d not in days:
            days[d] = []
        try:
            dt = datetime.fromisoformat(da) if "T" in da else datetime.strptime(da, "%Y-%m-%d")
            urgente = (dt - now).total_seconds() < 48 * 3600
        except Exception:
            urgente = False
        days[d].append({
            "orgao": r["orgao_nome"],
            "valor": r["valor_estimado"],
            "urgente": urgente,
            "status": r["status"],
        })

    return [{"date": d, "editais": eds} for d, eds in sorted(days.items())]


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
