"""Rotas de habilitação — gera declarações e pacotes automaticamente."""
import json
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agente_habilitacao.declaracao_builder import (
    gerar_pacote_completo, load_empresa, empresa_from_tenant,
    TIPOS_DISPONIVEIS, CONFIG_PATH, OUTPUT_DIR,
)
from api.deps import get_connection, tenant_filter_sql
from api.routes.auth import require_tenant, require_admin
from shared.database import get_tenant_empresas


router = APIRouter(prefix="/api/habilitacao", tags=["habilitacao"])


@router.get("/tipos")
def listar_tipos():
    """Lista todos os tipos de declaração disponíveis."""
    return [
        {"key": k, "nome": v["nome"], "ordem": v["ordem"]}
        for k, v in sorted(TIPOS_DISPONIVEIS.items(), key=lambda x: x[1]["ordem"])
    ]


@router.get("/empresas")
def listar_empresas(tenant: dict = Depends(require_tenant)):
    """Lista empresas do CLIENTE LOGADO (isolado por tenant). Nunca o config global."""
    empresas = get_tenant_empresas(tenant["id"]) or []
    # Mapeia pro shape que a tela de habilitação espera (razao_social/cnpj/...).
    out = []
    for e in empresas:
        out.append({
            "key": str(e.get("id")),
            "razao_social": e.get("nome") or e.get("razao_social") or "",
            "nome_fantasia": e.get("nome_fantasia", ""),
            "cnpj": e.get("cnpj") or "",
            "regime_tributario": e.get("regime_tributario", ""),
            "porte": e.get("porte", "ME"),
            "endereco": e.get("endereco", {}) if isinstance(e.get("endereco"), dict) else {},
            "contato": e.get("contato", {}) if isinstance(e.get("contato"), dict) else {},
            "representante_legal": e.get("representante_legal", {}) if isinstance(e.get("representante_legal"), dict) else {},
            "banco": e.get("banco", {}) if isinstance(e.get("banco"), dict) else {},
            "inscricao_estadual": e.get("inscricao_estadual", ""),
            "inscricao_municipal": e.get("inscricao_municipal", ""),
        })
    return out


class EmpresaUpdate(BaseModel):
    key: str
    razao_social: str
    nome_fantasia: str = ""
    cnpj: str
    inscricao_estadual: str = ""
    inscricao_municipal: str = ""
    endereco: dict
    contato: dict
    representante_legal: dict
    porte: str = "ME"
    regime_tributario: str = "Lucro Real"
    banco: dict = {}


@router.put("/empresas/{key}")
def atualizar_empresa(key: str, body: EmpresaUpdate, _admin: dict = Depends(require_admin)):
    """Atualiza o config GLOBAL de empresa — operador só. Cliente edita a empresa dele em /api/perfil."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    empresas = data.get("empresas", [])
    for i, e in enumerate(empresas):
        if e["key"] == key:
            empresas[i] = body.model_dump()
            break
    else:
        empresas.append(body.model_dump())

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"empresas": empresas}, f, ensure_ascii=False, indent=2)

    return {"ok": True}


class GerarPacoteRequest(BaseModel):
    empresa_id: int = None   # qual empresa do tenant usar (default: a 1ª)
    tipos: list[str] = None


@router.post("/edital/{pncp_id:path}/gerar")
def gerar_para_edital(pncp_id: str, body: GerarPacoteRequest = None,
                      tenant: dict = Depends(require_tenant)):
    """Gera o pacote de declarações com os dados da EMPRESA LOGADA (por tenant)."""
    body = body or GerarPacoteRequest()

    # Edital tem que pertencer ao tenant logado (isolamento).
    conn = get_connection()
    t_sql, t_params = tenant_filter_sql(tenant)
    row = conn.execute(
        f"SELECT * FROM editais WHERE pncp_id = ? AND {t_sql}", (pncp_id, *t_params)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Edital não encontrado")

    # Empresa do tenant → dados das declarações. Sem cadastro = avisa.
    empresas = get_tenant_empresas(tenant["id"]) or []
    if not empresas:
        raise HTTPException(400, "Cadastre os dados da sua empresa em Perfil antes de gerar a documentação.")
    if body.empresa_id:
        empresas = [e for e in empresas if e["id"] == body.empresa_id] or empresas
    empresa = empresa_from_tenant(empresas[0])

    edital_info = {
        "pncp_id": pncp_id,
        "orgao": row["orgao_nome"],
        "objeto": row["objeto"],
        "numero": row["pncp_id"],
        "municipio": row["municipio"],
        "uf": row["uf"],
    }

    try:
        zip_path = gerar_pacote_completo(edital_info, tipos=body.tipos, empresa=empresa)
    except Exception as e:
        raise HTTPException(500, f"Erro ao gerar pacote: {e}")

    return {
        "ok": True,
        "zip_path": str(zip_path),
        "download_url": f"/api/habilitacao/edital/{pncp_id}/download",
    }


@router.get("/edital/{pncp_id:path}/download")
def download_pacote(pncp_id: str):
    """Baixa o pacote ZIP gerado."""
    safe_id = pncp_id.replace("/", "_").replace("-", "_")
    zip_path = OUTPUT_DIR / safe_id / f"pacote_habilitacao_{safe_id}.zip"

    if not zip_path.exists():
        raise HTTPException(404, "Pacote não gerado. Gere primeiro via POST /gerar")

    return FileResponse(str(zip_path), filename=zip_path.name, media_type="application/zip")


@router.get("/edital/{pncp_id:path}/arquivos")
def listar_arquivos_gerados(pncp_id: str):
    """Lista arquivos do pacote gerado para um edital."""
    safe_id = pncp_id.replace("/", "_").replace("-", "_")
    pasta = OUTPUT_DIR / safe_id
    if not pasta.exists():
        return {"arquivos": [], "gerado": False}

    arquivos = []
    for f in sorted(pasta.glob("*.pdf")):
        arquivos.append({
            "nome": f.name,
            "tamanho_kb": round(f.stat().st_size / 1024, 1),
            "url": f"/api/habilitacao/edital/{pncp_id}/arquivo/{f.name}",
        })

    zip_path = pasta / f"pacote_habilitacao_{safe_id}.zip"
    return {
        "arquivos": arquivos,
        "gerado": True,
        "zip_disponivel": zip_path.exists(),
        "download_zip": f"/api/habilitacao/edital/{pncp_id}/download" if zip_path.exists() else None,
    }


@router.get("/edital/{pncp_id:path}/arquivo/{filename}")
def download_arquivo(pncp_id: str, filename: str):
    """Baixa uma declaração específica."""
    safe_id = pncp_id.replace("/", "_").replace("-", "_")
    pasta = OUTPUT_DIR / safe_id

    # Segurança: só permite arquivos dentro da pasta
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(403, "Nome inválido")

    file_path = pasta / filename
    if not file_path.exists():
        raise HTTPException(404, "Arquivo não encontrado")

    return FileResponse(str(file_path), filename=filename, media_type="application/pdf")
