"""Rotas de perfil — gerenciar empresas do tenant."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from api.routes.auth import require_tenant

router = APIRouter(prefix="/api/perfil", tags=["perfil"])


class EmpresaCreate(BaseModel):
    nome: str
    cnpj: str = None
    regime_tributario: str = "lucro_real"
    desonerada: bool = False
    cprb_pct: float = 4.5
    rat_pct: float = 3.0
    fap: float = 1.0
    pis_efetivo_pct: float = 1.65
    cofins_efetivo_pct: float = 7.6
    servicos: list[str] = []
    atestados: list[str] = []
    cnaes: list[str] = []
    uf_atuacao: list[str] = ["RJ"]
    restricoes: dict = {}


class EmpresaUpdate(BaseModel):
    nome: str = None
    cnpj: str = None
    regime_tributario: str = None
    desonerada: bool = None
    cprb_pct: float = None
    rat_pct: float = None
    fap: float = None
    pis_efetivo_pct: float = None
    cofins_efetivo_pct: float = None
    servicos: list[str] = None
    atestados: list[str] = None
    cnaes: list[str] = None
    uf_atuacao: list[str] = None
    restricoes: dict = None


@router.get("/empresas")
def listar_empresas(tenant: dict = Depends(require_tenant)):
    from shared.database import get_tenant_empresas
    empresas = get_tenant_empresas(tenant["id"])
    return [
        {
            "id": e["id"],
            "nome": e["nome"],
            "cnpj": e.get("cnpj"),
            "regime_tributario": e["regime_tributario"],
            "desonerada": bool(e["desonerada"]),
            "rat_ajustado_pct": e.get("rat_ajustado_pct", 3.0),
            "pis_efetivo_pct": e.get("pis_efetivo_pct", 1.65),
            "cofins_efetivo_pct": e.get("cofins_efetivo_pct", 7.6),
            "servicos": e.get("servicos_json", []),
            "atestados": e.get("atestados_json", []),
            "uf_atuacao": e.get("uf_atuacao_json", []),
        }
        for e in empresas
    ]


@router.post("/empresas")
def criar_empresa(body: EmpresaCreate, tenant: dict = Depends(require_tenant)):
    from shared.database import criar_tenant_empresa

    data = {
        "nome": body.nome,
        "cnpj": body.cnpj,
        "regime_tributario": body.regime_tributario,
        "desonerada": body.desonerada,
        "cprb_pct": body.cprb_pct,
        "rat_pct": body.rat_pct,
        "fap": body.fap,
        "rat_ajustado_pct": round(body.rat_pct * body.fap, 2),
        "pis_efetivo_pct": body.pis_efetivo_pct,
        "cofins_efetivo_pct": body.cofins_efetivo_pct,
        "servicos_json": body.servicos,
        "atestados_json": body.atestados,
        "cnaes_json": body.cnaes,
        "uf_atuacao_json": body.uf_atuacao,
        "restricoes_json": body.restricoes,
    }

    empresa_id = criar_tenant_empresa(tenant["id"], data)
    return {"id": empresa_id, "nome": body.nome}


@router.put("/empresas/{empresa_id}")
def atualizar_empresa(empresa_id: int, body: EmpresaUpdate, tenant: dict = Depends(require_tenant)):
    from shared.database import atualizar_tenant_empresa, get_tenant_empresas

    # Verifica se empresa pertence ao tenant
    empresas = get_tenant_empresas(tenant["id"])
    if not any(e["id"] == empresa_id for e in empresas):
        raise HTTPException(403, "Empresa não pertence ao seu cadastro")

    updates = {}
    for field, val in body.model_dump(exclude_none=True).items():
        if field in ("servicos", "atestados", "cnaes", "uf_atuacao", "restricoes"):
            updates[f"{field}_json"] = val
        else:
            updates[field] = val

    # Recalcula RAT ajustado se necessário
    if "rat_pct" in updates or "fap" in updates:
        rat = updates.get("rat_pct", 3.0)
        fap = updates.get("fap", 1.0)
        updates["rat_ajustado_pct"] = round(rat * fap, 2)

    if updates:
        atualizar_tenant_empresa(empresa_id, updates)

    return {"ok": True}


@router.delete("/empresas/{empresa_id}")
def deletar_empresa(empresa_id: int, tenant: dict = Depends(require_tenant)):
    from shared.database import deletar_tenant_empresa, get_tenant_empresas

    empresas = get_tenant_empresas(tenant["id"])
    if not any(e["id"] == empresa_id for e in empresas):
        raise HTTPException(403, "Empresa não pertence ao seu cadastro")

    deletar_tenant_empresa(empresa_id)
    return {"ok": True}
