"""Rotas de editais."""
import json
import asyncio
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from api.deps import get_connection

router = APIRouter(prefix="/api/editais", tags=["editais"])


@router.get("")
def listar_editais(
    status: list[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("-score_relevancia"),
    busca: str = Query(None),
):
    conn = get_connection()
    where = []
    params = []

    if status:
        placeholders = ",".join(["?"] * len(status))
        where.append(f"status IN ({placeholders})")
        params.extend(status)

    if busca:
        where.append("objeto LIKE ?")
        params.append(f"%{busca}%")

    where_sql = " AND ".join(where) if where else "1=1"

    # Sort
    sort_col = sort.lstrip("-")
    sort_dir = "DESC" if sort.startswith("-") else "ASC"
    allowed_sorts = {"score_relevancia", "valor_estimado", "created_at", "data_abertura", "data_encerramento"}
    if sort_col not in allowed_sorts:
        sort_col = "score_relevancia"
        sort_dir = "DESC"

    # Count
    count_row = conn.execute(f"SELECT COUNT(*) as total FROM editais WHERE {where_sql}", params).fetchone()
    total = count_row["total"]

    # Data
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM editais WHERE {where_sql} ORDER BY {sort_col} {sort_dir} NULLS LAST LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    items = []
    for r in rows:
        d = dict(r)
        for field in ("analise_json", "analise_competitiva_json"):
            if d.get(field) and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except json.JSONDecodeError:
                    pass
        items.append(d)

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/{pncp_id:path}")
def get_edital(pncp_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM editais WHERE pncp_id = ?", (pncp_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Edital não encontrado")

    d = dict(row)
    for field in ("analise_json", "analise_competitiva_json"):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except json.JSONDecodeError:
                pass

    # Comentários
    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE pncp_id = ? ORDER BY created_at ASC", (pncp_id,)
    ).fetchall()
    d["comentarios"] = [dict(c) for c in comentarios]

    return d


@router.post("/{pncp_id:path}/analisar")
def analisar_edital(pncp_id: str):
    import threading

    def _run():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from agente2_analista.main import analisar_edital as _analisar
        _analisar(pncp_id)

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "analisando", "pncp_id": pncp_id}


@router.post("/{pncp_id:path}/planilha")
def gerar_planilha(pncp_id: str):
    import threading

    def _run():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from agente3_precificador.main import precificar_edital
        precificar_edital(pncp_id)

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "precificando", "pncp_id": pncp_id}


@router.post("/{pncp_id:path}/competitivo")
def competitivo(pncp_id: str):
    import threading

    def _run():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from agente4_competitivo.main import analisar_edital_competitivo
        analisar_edital_competitivo(pncp_id)

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "processando", "pncp_id": pncp_id}


@router.post("/{pncp_id:path}/arquivar")
def arquivar_edital(pncp_id: str):
    conn = get_connection()
    conn.execute(
        "UPDATE editais SET status = 'arquivado', updated_at = datetime('now') WHERE pncp_id = ?",
        (pncp_id,),
    )
    conn.commit()
    return {"ok": True, "status": "arquivado"}


@router.get("/{pncp_id:path}/planilha/download")
def download_planilha(pncp_id: str):
    conn = get_connection()
    row = conn.execute("SELECT planilha_path FROM editais WHERE pncp_id = ?", (pncp_id,)).fetchone()
    if not row or not row["planilha_path"]:
        raise HTTPException(404, "Planilha não encontrada")

    path = Path(row["planilha_path"])
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado no servidor")

    return FileResponse(str(path), filename=path.name,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
