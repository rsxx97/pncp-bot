"""Autenticação SaaS — bcrypt + JWT + RBAC (super_admin / tenant_admin)."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
import bcrypt
import jwt

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def _verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8")[:72], senha_hash.encode("utf-8"))
    except Exception:
        return False


def _gerar_token(tenant_id: int, role: str) -> str:
    payload = {
        "sub": str(tenant_id),
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decodificar_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def get_current_tenant(authorization: str = Header(None)) -> dict | None:
    """Retorna tenant autenticado ou None se sem token / inválido."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    payload = _decodificar_token(token)
    if not payload:
        return None
    from shared.database import get_tenant
    tenant = get_tenant(int(payload["sub"]))
    if tenant:
        tenant["role"] = payload.get("role", tenant.get("role", "tenant_admin"))
    return tenant


def require_tenant(authorization: str = Header(...)) -> dict:
    tenant = get_current_tenant(authorization)
    if not tenant:
        raise HTTPException(401, "Token inválido ou expirado")
    if not tenant.get("ativo"):
        raise HTTPException(403, "Conta desativada")
    return tenant


def require_admin(tenant: dict = Depends(require_tenant)) -> dict:
    if tenant.get("role") != "super_admin":
        raise HTTPException(403, "Apenas administradores")
    return tenant


# ── Schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    nome_empresa: str
    email: EmailStr
    senha: str
    cnpj: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class TrocarSenhaRequest(BaseModel):
    senha_atual: str
    senha_nova: str


# ── Rotas ────────────────────────────────────────────────────────────

@router.post("/register")
def register(body: RegisterRequest):
    from shared.database import criar_tenant, get_tenant_by_email

    if get_tenant_by_email(body.email):
        raise HTTPException(409, "Email já cadastrado")

    if len(body.senha) < 6:
        raise HTTPException(400, "Senha precisa ter ao menos 6 caracteres")

    criar_tenant(
        nome_empresa=body.nome_empresa,
        email=body.email,
        senha_hash=_hash_senha(body.senha),
        cnpj=body.cnpj,
    )
    return {
        "message": "Cadastro realizado. Aguarde aprovação do administrador.",
        "pendente": True,
    }


@router.post("/login")
def login(body: LoginRequest):
    from shared.database import get_tenant_by_email

    tenant = get_tenant_by_email(body.email)
    if not tenant or not _verificar_senha(body.senha, tenant["senha_hash"]):
        raise HTTPException(401, "Email ou senha inválidos")

    if not tenant.get("ativo"):
        raise HTTPException(403, "Conta desativada")

    if not tenant.get("aprovado"):
        raise HTTPException(403, "Cadastro pendente de aprovação.")

    token = _gerar_token(tenant["id"], tenant.get("role", "tenant_admin"))
    return {
        "token": token,
        "tenant": {
            "id": tenant["id"],
            "nome_empresa": tenant["nome_empresa"],
            "email": tenant["email"],
            "plano": tenant["plano"],
            "plano_radar_limite": tenant.get("plano_radar_limite", 50),
            "role": tenant.get("role", "tenant_admin"),
            "senha_temporaria": bool(tenant.get("senha_temporaria", 0)),
        },
    }


@router.post("/senha")
def trocar_senha(body: TrocarSenhaRequest, tenant: dict = Depends(require_tenant)):
    from shared.database import atualizar_senha_tenant

    if not _verificar_senha(body.senha_atual, tenant["senha_hash"]):
        raise HTTPException(401, "Senha atual incorreta")

    if len(body.senha_nova) < 6:
        raise HTTPException(400, "Senha nova precisa ter ao menos 6 caracteres")

    atualizar_senha_tenant(tenant["id"], _hash_senha(body.senha_nova), senha_temporaria=0)
    return {"ok": True, "message": "Senha alterada"}


@router.get("/me")
def me(tenant: dict = Depends(require_tenant)):
    from shared.database import get_tenant_empresas
    empresas = get_tenant_empresas(tenant["id"])
    return {
        "id": tenant["id"],
        "nome_empresa": tenant["nome_empresa"],
        "email": tenant["email"],
        "plano": tenant["plano"],
        "plano_radar_limite": tenant.get("plano_radar_limite", 50),
        "role": tenant.get("role", "tenant_admin"),
        "senha_temporaria": bool(tenant.get("senha_temporaria", 0)),
        "empresas": [
            {
                "id": e["id"],
                "nome": e["nome"],
                "cnpj": e.get("cnpj"),
                "regime_tributario": e["regime_tributario"],
                "desonerada": bool(e["desonerada"]),
                "servicos": e.get("servicos_json", []),
                "atestados": e.get("atestados_json", []),
                "uf_atuacao": e.get("uf_atuacao_json", []),
            }
            for e in empresas
        ],
    }


# ── Admin (super_admin only) ─────────────────────────────────────────

@router.get("/pendentes")
def listar_pendentes(_admin: dict = Depends(require_admin)):
    from shared.database import listar_tenants
    return listar_tenants(somente_pendentes=True)


@router.get("/tenants")
def listar_todos_tenants(_admin: dict = Depends(require_admin)):
    from shared.database import listar_tenants
    return listar_tenants(somente_pendentes=False)


@router.post("/aprovar/{tenant_id}")
def aprovar_usuario(tenant_id: int, _admin: dict = Depends(require_admin)):
    from shared.database import get_db
    conn = get_db()
    conn.execute("UPDATE tenants SET aprovado = 1 WHERE id = ?", (tenant_id,))
    conn.commit()
    return {"ok": True, "message": "Tenant aprovado"}


@router.post("/rejeitar/{tenant_id}")
def rejeitar_usuario(tenant_id: int, _admin: dict = Depends(require_admin)):
    from shared.database import get_db
    conn = get_db()
    conn.execute("UPDATE tenants SET ativo = 0 WHERE id = ?", (tenant_id,))
    conn.commit()
    return {"ok": True, "message": "Tenant desativado"}
