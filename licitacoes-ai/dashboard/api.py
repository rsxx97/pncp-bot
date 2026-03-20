"""Dashboard API — FastAPI backend."""
import json
import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import (
    init_db, get_db, get_edital, get_editais_recentes, get_editais_pendentes,
    atualizar_status_edital, contar_editais_por_status, get_custo_total,
    get_monitor_state, set_monitor_state, listar_comentarios,
    adicionar_comentario, listar_concorrentes, get_execucoes_recentes,
)
from shared.utils import formatar_valor

log = logging.getLogger("dashboard_api")

app = FastAPI(title="Licitações AI Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


@app.on_event("startup")
def startup():
    init_db()


# ── Stats ────────────────────────────────────────────────────────

@app.get("/api/stats")
def api_stats():
    contagem = contar_editais_por_status()
    custo_30d = get_custo_total(30)
    custo_7d = get_custo_total(7)
    monitor = get_monitor_state()

    total = sum(contagem.values())
    go = contagem.get("analisado", 0) + contagem.get("precificado", 0) + contagem.get("competitivo_pronto", 0)
    nogo = contagem.get("nogo", 0) + contagem.get("descartado", 0)

    return {
        "total_editais": total,
        "por_status": contagem,
        "aprovados": go,
        "rejeitados": nogo,
        "taxa_aprovacao": round(go / (go + nogo) * 100, 1) if (go + nogo) > 0 else 0,
        "custo_api_7d": round(custo_7d, 4),
        "custo_api_30d": round(custo_30d, 4),
        "monitor_ativo": monitor.get("ativo", False),
        "ultima_consulta": monitor.get("ultima_consulta"),
    }


# ── Editais ──────────────────────────────────────────────────────

@app.get("/api/editais")
def api_editais(
    status: str = Query(None),
    uf: str = Query(None),
    busca: str = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    conn = get_db()

    where = []
    params = []

    if status:
        where.append("status = ?")
        params.append(status)
    if uf:
        where.append("uf = ?")
        params.append(uf)
    if busca:
        where.append("objeto LIKE ?")
        params.append(f"%{busca}%")

    where_sql = " AND ".join(where) if where else "1=1"

    # Count
    count_row = conn.execute(
        f"SELECT COUNT(*) as total FROM editais WHERE {where_sql}", params
    ).fetchone()
    total = count_row["total"]

    # Data
    rows = conn.execute(
        f"SELECT * FROM editais WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    editais = []
    for r in rows:
        e = dict(r)
        # Parse JSON fields
        for field in ("analise_json", "analise_competitiva_json"):
            if e.get(field) and isinstance(e[field], str):
                try:
                    e[field] = json.loads(e[field])
                except json.JSONDecodeError:
                    pass
        editais.append(e)

    return {"total": total, "editais": editais}


@app.get("/api/editais/{pncp_id:path}")
def api_edital_detalhe(pncp_id: str):
    edital = get_edital(pncp_id)
    if not edital:
        raise HTTPException(404, "Edital não encontrado")

    for field in ("analise_json", "analise_competitiva_json"):
        if edital.get(field) and isinstance(edital[field], str):
            try:
                edital[field] = json.loads(edital[field])
            except json.JSONDecodeError:
                pass

    # Comentários
    edital["comentarios"] = listar_comentarios(pncp_id)

    return edital


@app.put("/api/editais/{pncp_id:path}/status")
def api_atualizar_status(pncp_id: str, body: dict):
    novo_status = body.get("status")
    if not novo_status:
        raise HTTPException(400, "status é obrigatório")

    edital = get_edital(pncp_id)
    if not edital:
        raise HTTPException(404, "Edital não encontrado")

    atualizar_status_edital(pncp_id, novo_status)
    return {"ok": True, "status": novo_status}


@app.post("/api/editais/{pncp_id:path}/comentario")
def api_adicionar_comentario(pncp_id: str, body: dict):
    texto = body.get("texto", "").strip()
    if not texto:
        raise HTTPException(400, "texto é obrigatório")

    edital = get_edital(pncp_id)
    if not edital:
        raise HTTPException(404, "Edital não encontrado")

    cid = adicionar_comentario(
        pncp_id=pncp_id,
        texto=texto,
        tipo=body.get("tipo", "anotacao"),
        autor=body.get("autor", "Usuário"),
    )
    return {"ok": True, "id": cid}


# ── Pipeline ─────────────────────────────────────────────────────

@app.post("/api/editais/{pncp_id:path}/analisar")
def api_analisar(pncp_id: str):
    import threading

    def _run():
        try:
            from agente2_analista.main import analisar_edital
            analisar_edital(pncp_id)
        except Exception as e:
            log.error(f"Erro análise: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "msg": "Análise iniciada"}


@app.post("/api/editais/{pncp_id:path}/precificar")
def api_precificar(pncp_id: str):
    import threading

    def _run():
        try:
            from agente3_precificador.main import precificar_edital
            precificar_edital(pncp_id)
        except Exception as e:
            log.error(f"Erro precificação: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "msg": "Precificação iniciada"}


@app.post("/api/editais/{pncp_id:path}/competitivo")
def api_competitivo(pncp_id: str):
    import threading

    def _run():
        try:
            from agente4_competitivo.main import analisar_edital_competitivo
            analisar_edital_competitivo(pncp_id)
        except Exception as e:
            log.error(f"Erro competitivo: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "msg": "Análise competitiva iniciada"}


@app.post("/api/editais/{pncp_id:path}/pipeline")
def api_pipeline(pncp_id: str):
    """Executa pipeline completo: análise → precificação → competitivo."""
    import threading

    def _run():
        try:
            from agente2_analista.main import analisar_edital
            from agente3_precificador.main import precificar_edital
            from agente4_competitivo.main import analisar_edital_competitivo

            analisar_edital(pncp_id)
            precificar_edital(pncp_id)
            analisar_edital_competitivo(pncp_id)
        except Exception as e:
            log.error(f"Erro pipeline: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "msg": "Pipeline completo iniciado"}


# ── Monitor ──────────────────────────────────────────────────────

@app.post("/api/monitor/executar")
def api_executar_monitor():
    import threading

    def _run():
        try:
            from agente1_monitor.main import executar_monitor
            executar_monitor()
        except Exception as e:
            log.error(f"Erro monitor: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "msg": "Monitor iniciado"}


@app.get("/api/monitor/status")
def api_monitor_status():
    return get_monitor_state()


@app.post("/api/monitor/toggle")
def api_monitor_toggle():
    monitor = get_monitor_state()
    novo = not monitor.get("ativo", False)
    set_monitor_state(ativo=novo)
    return {"ativo": novo}


# ── Relatórios ───────────────────────────────────────────────────

@app.get("/api/relatorios/por-uf")
def api_relatorio_uf():
    conn = get_db()
    rows = conn.execute(
        "SELECT uf, COUNT(*) as total, COALESCE(SUM(valor_estimado), 0) as valor_total "
        "FROM editais WHERE uf IS NOT NULL AND uf != '' "
        "GROUP BY uf ORDER BY valor_total DESC LIMIT 15"
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/relatorios/por-modalidade")
def api_relatorio_modalidade():
    conn = get_db()
    rows = conn.execute(
        "SELECT modalidade, COUNT(*) as total "
        "FROM editais WHERE modalidade IS NOT NULL "
        "GROUP BY modalidade ORDER BY total DESC"
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/relatorios/timeline")
def api_relatorio_timeline():
    conn = get_db()
    rows = conn.execute(
        "SELECT DATE(created_at) as data, COUNT(*) as total "
        "FROM editais "
        "GROUP BY DATE(created_at) ORDER BY data DESC LIMIT 30"
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/relatorios/execucoes")
def api_relatorio_execucoes():
    return get_execucoes_recentes(limit=50)


# ── Concorrentes ─────────────────────────────────────────────────

@app.get("/api/concorrentes")
def api_concorrentes():
    return listar_concorrentes()


# ── Planilha download ────────────────────────────────────────────

@app.get("/api/editais/{pncp_id:path}/planilha")
def api_download_planilha(pncp_id: str):
    edital = get_edital(pncp_id)
    if not edital or not edital.get("planilha_path"):
        raise HTTPException(404, "Planilha não encontrada")

    path = Path(edital["planilha_path"])
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado no servidor")

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── Frontend SPA ─────────────────────────────────────────────────

@app.get("/")
def serve_frontend():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Licitações AI Dashboard</h1><p>Frontend não encontrado em /dashboard/static/index.html</p>")


# Mount static
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
