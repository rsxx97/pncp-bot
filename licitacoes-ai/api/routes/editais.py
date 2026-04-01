"""Rotas de editais."""
import json
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.deps import get_connection


class PostoManual(BaseModel):
    funcao: str
    quantidade: int = 1
    jornada: str = "44h"


class PostosManuaisRequest(BaseModel):
    postos: list[PostoManual]

router = APIRouter(prefix="/api/editais", tags=["editais"])


# ──────────────────────────────────────────────
# Rotas sem path param (devem vir primeiro)
# ──────────────────────────────────────────────

@router.get("/empresas/listar")
def listar_empresas():
    """Lista empresas do grupo disponíveis para precificação."""
    import json as _json
    perfil_path = Path(__file__).parent.parent.parent / "config" / "empresa_perfil.json"
    with open(perfil_path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    return [
        {
            "nome": e["nome"],
            "regime": e.get("regime_tributario", ""),
            "desonerada": e.get("desonerada", False),
            "servicos": e.get("servicos", []),
            "uf_atuacao": e.get("uf_atuacao", []),
        }
        for e in data["empresas"]
    ]


@router.get("/mdo/perfis")
def listar_perfis_mdo():
    """Lista perfis de MDO padrão disponíveis."""
    import json as _json
    mdo_path = Path(__file__).parent.parent.parent / "config" / "mdo_padrao.json"
    with open(mdo_path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    perfis = data.get("perfis", {})
    return [
        {
            "key": k,
            "nome": v.get("nome", k),
            "empresa_preferida": v.get("empresa_preferida", ""),
            "postos": v.get("postos", []),
            "total_funcionarios": sum(p.get("quantidade", 1) for p in v.get("postos", [])),
        }
        for k, v in perfis.items()
    ]


@router.get("/pncp/buscar")
def buscar_pncp(
    q: str = Query(..., min_length=2),
    uf: str = Query(None),
    municipio: str = Query(None),
    modalidade: str = Query(None),
    valor_min: float = Query(None),
    valor_max: float = Query(None),
):
    """Busca editais no PNCP por texto com filtros opcionais."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from agente1_monitor.pncp_client import buscar_editais_por_texto
    # Busca mais resultados para permitir filtros client-side eficazes
    items = buscar_editais_por_texto(q, tam_pagina=50, paginas=3)

    # Aplica filtros server-side
    filtered = []
    for it in items:
        if not it.get("pncp_id"):
            continue
        if uf and it.get("uf", "").upper() != uf.upper():
            continue
        if municipio and municipio.lower() not in (it.get("municipio_nome") or "").lower():
            continue
        if modalidade and modalidade.lower() not in (it.get("modalidade_licitacao_nome") or "").lower():
            continue
        v = it.get("valor_global")
        if valor_min is not None and (v is None or v < valor_min):
            continue
        if valor_max is not None and (v is not None and v > valor_max):
            continue
        filtered.append(it)

    conn = get_connection()
    pncp_ids = [it.get("pncp_id") for it in filtered]
    ids_existentes = set()
    if pncp_ids:
        placeholders = ",".join(["?"] * len(pncp_ids))
        rows = conn.execute(f"SELECT pncp_id FROM editais WHERE pncp_id IN ({placeholders})", pncp_ids).fetchall()
        ids_existentes = {r["pncp_id"] for r in rows}

    # Coleta UFs e municipios únicos para os dropdowns do frontend
    all_ufs = sorted({it.get("uf", "") for it in items if it.get("uf")})
    all_municipios = sorted({it.get("municipio_nome", "") for it in items if it.get("municipio_nome")})
    all_modalidades = sorted({it.get("modalidade_licitacao_nome", "") for it in items if it.get("modalidade_licitacao_nome")})

    results = [
        {
            "pncp_id": it.get("pncp_id", ""),
            "orgao": it.get("orgao_nome", ""),
            "objeto": it.get("description", ""),
            "valor_estimado": it.get("valor_global"),
            "uf": it.get("uf", ""),
            "municipio": it.get("municipio_nome", ""),
            "modalidade": it.get("modalidade_licitacao_nome", ""),
            "data_abertura": it.get("data_inicio_vigencia"),
            "data_encerramento": it.get("data_fim_vigencia"),
            "link_edital": f"https://pncp.gov.br/app/editais/{it.get('item_url', '').replace('/compras/', '')}" if it.get("item_url") else "",
            "ja_importado": it.get("pncp_id", "") in ids_existentes,
        }
        for it in filtered
    ]

    return {
        "items": results,
        "total": len(results),
        "filtros": {"ufs": all_ufs, "municipios": all_municipios, "modalidades": all_modalidades},
    }


class ImportarPncpRequest(BaseModel):
    pncp_ids: list[str]


@router.post("/pncp/importar")
def importar_editais_pncp(body: ImportarPncpRequest):
    """Importa editais do PNCP para o dashboard com IDs reais."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from agente1_monitor.pncp_client import buscar_edital_por_id
    from agente1_monitor.classifier import classificar_rapido

    conn = get_connection()
    importados = []
    ja_existem = []

    for pncp_id in body.pncp_ids:
        existing = conn.execute("SELECT pncp_id FROM editais WHERE pncp_id = ?", (pncp_id,)).fetchone()
        if existing:
            ja_existem.append(pncp_id)
            continue

        parts = pncp_id.split("-")
        if len(parts) < 3:
            continue

        cnpj, ano, seq = parts[0], parts[1], parts[2]
        edital = buscar_edital_por_id(cnpj, int(ano), int(seq))
        if not edital:
            continue

        try:
            cl = classificar_rapido(edital)
            score, justificativa, empresa = cl.score, cl.justificativa, cl.empresa_sugerida
        except Exception:
            score, justificativa, empresa = 50, "Importado manualmente via PNCP", ""

        conn.execute(
            """INSERT INTO editais (pncp_id, orgao_cnpj, orgao_nome, objeto, valor_estimado,
               data_publicacao, data_abertura, data_encerramento, modalidade, modalidade_cod,
               uf, municipio, link_edital, fonte, score_relevancia, justificativa_score,
               empresa_sugerida, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pncp', ?, ?, ?, 'novo',
               datetime('now'), datetime('now'))""",
            (pncp_id, edital.orgao_cnpj, edital.orgao_nome, edital.objeto,
             edital.valor_estimado, edital.data_publicacao, edital.data_abertura,
             edital.data_encerramento, edital.modalidade, edital.modalidade_cod,
             edital.uf, edital.municipio, edital.link_edital,
             score, justificativa, empresa or ""),
        )
        importados.append(pncp_id)

    conn.commit()
    return {"ok": True, "importados": len(importados), "ja_existiam": len(ja_existem), "ids": importados}


class EditalManual(BaseModel):
    orgao: str
    objeto: str
    valor_estimado: float = 0
    uf: str = "RJ"
    municipio: str = ""
    data_abertura: str = ""
    data_encerramento: str = ""
    numero: str = ""
    portal: str = ""
    requisitos: str = ""


@router.post("/manual/inserir")
def inserir_edital_manual(body: EditalManual):
    """Insere edital manualmente no dashboard (ex: licitações do Keeping)."""
    import hashlib
    conn = get_connection()

    # Gera um pncp_id fake para editais manuais (MANUAL-hash)
    hash_str = f"{body.orgao}-{body.numero}-{body.objeto[:50]}"
    hash_id = hashlib.md5(hash_str.encode()).hexdigest()[:12]
    pncp_id = f"MANUAL-{hash_id}"

    # Verifica se já existe
    existing = conn.execute("SELECT pncp_id FROM editais WHERE pncp_id = ?", (pncp_id,)).fetchone()
    if existing:
        return {"ok": True, "pncp_id": pncp_id, "status": "ja_existe"}

    conn.execute(
        """INSERT INTO editais (pncp_id, orgao_nome, objeto, valor_estimado, uf, municipio,
           data_abertura, data_encerramento, status, score_relevancia, created_at, updated_at, fonte)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'novo', 75, datetime('now'), datetime('now'), 'manual')""",
        (pncp_id, body.orgao, body.objeto, body.valor_estimado, body.uf, body.municipio,
         body.data_abertura, body.data_encerramento),
    )
    conn.commit()
    return {"ok": True, "pncp_id": pncp_id, "status": "inserido"}


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

    sort_col = sort.lstrip("-")
    sort_dir = "DESC" if sort.startswith("-") else "ASC"
    allowed_sorts = {"score_relevancia", "valor_estimado", "created_at", "data_abertura", "data_encerramento"}
    if sort_col not in allowed_sorts:
        sort_col = "score_relevancia"
        sort_dir = "DESC"

    count_row = conn.execute(f"SELECT COUNT(*) as total FROM editais WHERE {where_sql}", params).fetchone()
    total = count_row["total"]

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


# ──────────────────────────────────────────────
# Rotas com path param ESPECÍFICO (antes do catch-all)
# Formato pncp_id: CNPJ-ANO-SEQ (ex: 42498600000171-2026-1256)
# ──────────────────────────────────────────────

# --- PDF ---

@router.get("/{pncp_id:path}/pdf/download")
def download_pdf_edital(pncp_id: str):
    """Baixa o PDF do edital. Se já está em cache, serve direto. Senão, baixa do PNCP."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import EDITAIS_DIR

    pdf_path = EDITAIS_DIR / f"{pncp_id}.pdf"

    if pdf_path.exists():
        return FileResponse(str(pdf_path), filename=f"edital_{pncp_id}.pdf",
                            media_type="application/pdf")

    # Tenta baixar do PNCP (só funciona com IDs no formato CNPJ-ANO-SEQ)
    parts = pncp_id.split("-")
    if len(parts) < 3 or pncp_id.startswith("MANUAL"):
        raise HTTPException(404, "PDF não disponível para editais manuais")

    try:
        from agente1_monitor.pncp_client import buscar_arquivos_compra
        from agente2_analista.pdf_extractor import download_pdf

        cnpj, ano, seq = parts[0], parts[1], parts[2]
        arquivos = buscar_arquivos_compra(cnpj, int(ano), int(seq))
        if not arquivos:
            raise HTTPException(404, "Nenhum arquivo encontrado no PNCP")

        chosen = arquivos[0]
        for arq in arquivos:
            titulo = (arq.get("titulo", "") or "").lower()
            if "edital" in titulo:
                chosen = arq
                break

        url = chosen.get("url") or chosen.get("uri")
        if not url:
            raise HTTPException(404, "URL do arquivo não encontrada")

        pdf_path = download_pdf(url, f"{pncp_id}.pdf")
        return FileResponse(str(pdf_path), filename=f"edital_{pncp_id}.pdf",
                            media_type="application/pdf")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao baixar PDF: {str(e)}")


@router.get("/{pncp_id:path}/pdf/download_TR")
def download_pdf_tr(pncp_id: str):
    """Baixa o Termo de Referência."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import EDITAIS_DIR

    pdf_path = EDITAIS_DIR / f"{pncp_id}_TR.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "Termo de Referência não encontrado")

    return FileResponse(str(pdf_path), filename=f"TR_{pncp_id}.pdf",
                        media_type="application/pdf")


@router.get("/{pncp_id:path}/pdf/arquivos")
def listar_arquivos_pncp(pncp_id: str):
    """Lista todos os arquivos disponíveis no PNCP para este edital."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import EDITAIS_DIR

    local_files = []
    # Busca TODOS os arquivos locais com prefixo do pncp_id
    import glob as _glob
    pattern = str(EDITAIS_DIR / f"{pncp_id}*")
    for fpath in sorted(_glob.glob(pattern)):
        fp = Path(fpath)
        fname = fp.name.replace(f"{pncp_id}_", "").replace(f"{pncp_id}", "")
        if fname.startswith("_"):
            fname = fname[1:]
        # Label amigável
        titulo = fname.replace("_", " ").replace(".pdf", "").replace(".xlsx", " (XLSX)").strip()
        if not titulo:
            titulo = "Edital"
        local_files.append({
            "titulo": titulo,
            "url": f"/api/editais/{pncp_id}/pdf/download_local/{fp.name}",
            "local": True,
            "tamanho_kb": round(fp.stat().st_size / 1024),
        })

    # Tenta buscar arquivos do PNCP (só para IDs no formato CNPJ-ANO-SEQ)
    arquivos_pncp = []
    parts = pncp_id.split("-")
    if len(parts) >= 3 and not pncp_id.startswith("MANUAL"):
        try:
            from agente1_monitor.pncp_client import buscar_arquivos_compra
            cnpj, ano, seq = parts[0], parts[1], parts[2]
            arquivos_pncp = buscar_arquivos_compra(cnpj, int(ano), int(seq))
        except Exception:
            arquivos_pncp = []

    remote_files = []
    for arq in arquivos_pncp:
        remote_files.append({
            "titulo": arq.get("titulo", "Arquivo"),
            "url": arq.get("url") or arq.get("uri"),
            "local": False,
        })

    return {"local": local_files, "pncp": remote_files}


@router.get("/{pncp_id:path}/pdf/download_local/{filename}")
def download_local_file(pncp_id: str, filename: str):
    """Baixa qualquer arquivo local associado ao edital."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import EDITAIS_DIR

    # Segurança: só permite arquivos que começam com o pncp_id
    if not filename.startswith(pncp_id):
        raise HTTPException(403, "Acesso negado")

    file_path = EDITAIS_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "Arquivo não encontrado")

    # Detecta media type
    ext = file_path.suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    media = media_types.get(ext, "application/octet-stream")

    return FileResponse(str(file_path), filename=filename, media_type=media)


@router.get("/{pncp_id:path}/pdf/download_arquivo/{idx}")
def download_arquivo_pncp(pncp_id: str, idx: int):
    """Baixa um arquivo específico do PNCP pelo índice na lista de arquivos."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import EDITAIS_DIR

    parts = pncp_id.split("-")
    if len(parts) < 3 or pncp_id.startswith("MANUAL"):
        raise HTTPException(404, "Arquivos não disponíveis para editais manuais")

    from agente1_monitor.pncp_client import buscar_arquivos_compra
    cnpj, ano, seq = parts[0], parts[1], parts[2]
    arquivos = buscar_arquivos_compra(cnpj, int(ano), int(seq))

    if idx < 0 or idx >= len(arquivos):
        raise HTTPException(404, f"Arquivo {idx} não encontrado")

    arq = arquivos[idx]
    url = arq.get("url") or arq.get("uri")
    titulo = arq.get("titulo", f"arquivo_{idx}")
    if not url:
        raise HTTPException(404, "URL do arquivo não encontrada")

    # Baixa e serve
    import httpx
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in titulo)
    cache_path = EDITAIS_DIR / f"{pncp_id}_doc_{idx}.pdf"

    if cache_path.exists():
        return FileResponse(str(cache_path), filename=safe_name,
                            media_type="application/pdf")

    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url if url.startswith("http") else f"https://pncp.gov.br{url}")
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)
        return FileResponse(str(cache_path), filename=safe_name,
                            media_type="application/pdf")
    except Exception as e:
        raise HTTPException(500, f"Erro ao baixar: {str(e)}")


# --- Planilha ---

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


@router.post("/{pncp_id:path}/planilha/upload")
async def upload_planilha(pncp_id: str, file: UploadFile = File(...)):
    """Upload manual de planilha pelo usuário."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import PLANILHAS_DIR

    if not file.filename.endswith((".xlsx", ".xls", ".ods")):
        raise HTTPException(400, "Arquivo deve ser .xlsx, .xls ou .ods")

    PLANILHAS_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = pncp_id.replace("/", "_").replace("\\", "_")
    dest = PLANILHAS_DIR / f"planilha_{safe_id}_manual.xlsx"

    content = await file.read()
    dest.write_bytes(content)

    conn = get_connection()
    conn.execute(
        "UPDATE editais SET planilha_path = ?, status = CASE WHEN status IN ('novo','classificado','analisado','go','go_com_ressalvas','go_sem_ressalvas') THEN 'precificado' ELSE status END, updated_at = datetime('now') WHERE pncp_id = ?",
        (str(dest), pncp_id)
    )
    conn.commit()

    size_kb = len(content) // 1024
    return {"ok": True, "path": str(dest), "filename": file.filename, "size_kb": size_kb}


# --- Ações (POST) ---

@router.post("/{pncp_id:path}/resetar")
def resetar_edital(pncp_id: str):
    """Reseta o status do edital para 'novo', limpando erros."""
    conn = get_connection()
    conn.execute(
        "UPDATE editais SET status = 'novo', updated_at = datetime('now') WHERE pncp_id = ?",
        (pncp_id,)
    )
    conn.commit()
    return {"ok": True, "status": "novo"}


@router.delete("/{pncp_id:path}/excluir")
def excluir_edital(pncp_id: str):
    """Exclui edital do pipeline."""
    conn = get_connection()
    conn.execute("DELETE FROM editais WHERE pncp_id = ?", (pncp_id,))
    conn.commit()
    return {"ok": True}


@router.put("/{pncp_id:path}/atualizar")
def atualizar_edital(pncp_id: str, body: dict):
    """Atualiza campos do edital."""
    conn = get_connection()
    allowed = ["orgao_nome", "objeto", "valor_estimado", "uf", "municipio", "uasg", "portal", "data_abertura", "data_encerramento"]
    updates = []
    values = []
    for k, v in body.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            values.append(v)
    if not updates:
        return {"ok": False, "error": "Nenhum campo válido"}
    values.append(pncp_id)
    conn.execute(f"UPDATE editais SET {', '.join(updates)}, updated_at = datetime('now') WHERE pncp_id = ?", values)
    conn.commit()
    return {"ok": True}


@router.post("/{pncp_id:path}/analisar")
def analisar_edital(pncp_id: str):
    import threading

    TIMEOUT_SEG = 300  # 5 minutos

    def _run():
        import sys, time
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from agente2_analista.main import analisar_edital as _analisar
        from shared.database import atualizar_status_edital, get_edital
        try:
            _analisar(pncp_id)
        except Exception as e:
            # Se deu erro, volta status para permitir retry
            ed = get_edital(pncp_id)
            if ed and ed["status"] == "analisando":
                atualizar_status_edital(pncp_id, "erro_analise")

    def _run_with_timeout():
        import time
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=TIMEOUT_SEG)
        if t.is_alive():
            # Thread ainda rodando após timeout — marca erro
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from shared.database import atualizar_status_edital, get_edital
            ed = get_edital(pncp_id)
            if ed and ed["status"] == "analisando":
                atualizar_status_edital(pncp_id, "erro_analise")

    threading.Thread(target=_run_with_timeout, daemon=True).start()
    return {"status": "analisando", "pncp_id": pncp_id}


@router.post("/{pncp_id:path}/planilha")
def gerar_planilha(pncp_id: str):
    import threading, logging
    log = logging.getLogger("rota_planilha")

    # Atualiza status ANTES de iniciar
    conn = get_connection()
    conn.execute("UPDATE editais SET status = 'precificando', updated_at = datetime('now') WHERE pncp_id = ?", (pncp_id,))
    conn.commit()

    TIMEOUT_SEG = 300

    def _run():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from agente3_precificador.main import precificar_edital
        from shared.database import atualizar_status_edital, get_edital
        try:
            log.info(f"Iniciando precificacao: {pncp_id}")
            precificar_edital(pncp_id)
            log.info(f"Precificacao concluida: {pncp_id}")
        except Exception as e:
            log.error(f"Erro na precificacao {pncp_id}: {e}", exc_info=True)
            ed = get_edital(pncp_id)
            if ed and ed["status"] == "precificando":
                atualizar_status_edital(pncp_id, "erro_precificacao")

    def _run_with_timeout():
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=TIMEOUT_SEG)
        if t.is_alive():
            log.error(f"Timeout precificacao {pncp_id}")
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from shared.database import atualizar_status_edital, get_edital
            ed = get_edital(pncp_id)
            if ed and ed["status"] == "precificando":
                atualizar_status_edital(pncp_id, "erro_precificacao")

    threading.Thread(target=_run_with_timeout, daemon=True).start()
    return {"status": "precificando", "pncp_id": pncp_id}


@router.post("/{pncp_id:path}/postos-manual")
def adicionar_postos_manual(pncp_id: str, body: PostosManuaisRequest):
    """Recebe postos de trabalho manualmente e salva na análise para precificação."""
    conn = get_connection()

    row = conn.execute("SELECT analise_json FROM editais WHERE pncp_id = ?", (pncp_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Edital não encontrado")

    analise = {}
    if row["analise_json"]:
        try:
            analise = json.loads(row["analise_json"]) if isinstance(row["analise_json"], str) else row["analise_json"]
        except json.JSONDecodeError:
            analise = {}

    postos_manuais = []
    for p in body.postos:
        postos_manuais.append({
            "funcao": p.funcao.lower().replace(" ", "_"),
            "funcao_display": p.funcao,
            "quantidade": p.quantidade,
            "jornada": p.jornada,
        })

    analise["postos_trabalho"] = postos_manuais
    analise["_postos_fonte"] = "manual"

    conn.execute(
        "UPDATE editais SET analise_json = ?, status = CASE WHEN status IN ('novo', 'classificado') THEN 'go' ELSE status END, updated_at = datetime('now') WHERE pncp_id = ?",
        (json.dumps(analise, ensure_ascii=False), pncp_id),
    )
    conn.commit()

    return {"ok": True, "pncp_id": pncp_id, "postos": len(postos_manuais), "status": "Postos salvos. Agora gere a planilha."}


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


# ──────────────────────────────────────────────
# Rota catch-all GET (DEVE ser a última)
# ──────────────────────────────────────────────

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

    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE pncp_id = ? ORDER BY created_at ASC", (pncp_id,)
    ).fetchall()
    d["comentarios"] = [dict(c) for c in comentarios]

    return d
