"""Rotas de autenticação — registro, login, perfil."""
import hashlib
import secrets
import time
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr

from api.deps import get_connection

router = APIRouter(prefix="/api/auth", tags=["auth"])

# JWT simplificado com HMAC-SHA256
_SECRET = "licitacoes-ai-secret-key-2026"  # Em produção, usar env var


def _hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def _gerar_token(tenant_id: int) -> str:
    """Gera token simples: tenant_id.timestamp.signature"""
    payload = f"{tenant_id}.{int(time.time())}"
    sig = hashlib.sha256(f"{payload}.{_SECRET}".encode()).hexdigest()[:16]
    return f"{payload}.{sig}"


def _verificar_token(token: str) -> int | None:
    """Verifica token e retorna tenant_id ou None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        tenant_id, ts, sig = int(parts[0]), int(parts[1]), parts[2]
        expected = hashlib.sha256(f"{tenant_id}.{ts}.{_SECRET}".encode()).hexdigest()[:16]
        if sig != expected:
            return None
        # Token válido por 30 dias
        if time.time() - ts > 30 * 86400:
            return None
        return tenant_id
    except (ValueError, IndexError):
        return None


def get_current_tenant(authorization: str = Header(None)) -> dict | None:
    """Dependency: extrai tenant do header Authorization.
    Retorna None se não autenticado (permite acesso público).
    """
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    tenant_id = _verificar_token(token)
    if not tenant_id:
        return None

    from shared.database import get_tenant
    return get_tenant(tenant_id)


def require_tenant(authorization: str = Header(...)) -> dict:
    """Dependency: exige autenticação."""
    tenant = get_current_tenant(authorization)
    if not tenant:
        raise HTTPException(401, "Token inválido ou expirado")
    return tenant


# ── Schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    nome_empresa: str
    email: str
    senha: str
    cnpj: str | None = None


class LoginRequest(BaseModel):
    email: str
    senha: str


# ── Rotas ────────────────────────────────────────────────────────────

@router.post("/register")
def register(body: RegisterRequest):
    from shared.database import criar_tenant, get_tenant_by_email

    existing = get_tenant_by_email(body.email)
    if existing:
        raise HTTPException(409, "Email já cadastrado")

    tenant_id = criar_tenant(
        nome_empresa=body.nome_empresa,
        email=body.email,
        senha_hash=_hash_senha(body.senha),
        cnpj=body.cnpj,
    )

    return {
        "message": "Cadastro realizado! Aguarde aprovação do administrador.",
        "pendente": True,
    }


@router.post("/login")
def login(body: LoginRequest):
    from shared.database import get_tenant_by_email

    tenant = get_tenant_by_email(body.email)
    if not tenant or tenant["senha_hash"] != _hash_senha(body.senha):
        raise HTTPException(401, "Email ou senha inválidos")

    if not tenant["ativo"]:
        raise HTTPException(403, "Conta desativada")

    # Verifica aprovação
    conn = get_connection()
    row = conn.execute("SELECT aprovado FROM tenants WHERE id = ?", (tenant["id"],)).fetchone()
    if row and not row["aprovado"]:
        raise HTTPException(403, "Cadastro pendente de aprovação. Entre em contato com o administrador.")

    token = _gerar_token(tenant["id"])
    return {
        "token": token,
        "tenant": {
            "id": tenant["id"],
            "nome_empresa": tenant["nome_empresa"],
            "email": tenant["email"],
            "plano": tenant["plano"],
        },
    }


# ── Admin: aprovar/rejeitar usuários ──

@router.get("/pendentes")
def listar_pendentes():
    """Lista usuários aguardando aprovação."""
    conn = get_connection()
    rows = conn.execute("SELECT id, nome_empresa, email, cnpj, criado_em FROM tenants WHERE aprovado = 0 AND ativo = 1").fetchall()
    return [dict(r) for r in rows]


@router.post("/aprovar/{tenant_id}")
def aprovar_usuario(tenant_id: int):
    """Aprova um usuário pendente."""
    conn = get_connection()
    conn.execute("UPDATE tenants SET aprovado = 1 WHERE id = ?", (tenant_id,))
    conn.commit()
    return {"ok": True, "message": "Usuário aprovado"}


@router.post("/rejeitar/{tenant_id}")
def rejeitar_usuario(tenant_id: int):
    """Rejeita/desativa um usuário."""
    conn = get_connection()
    conn.execute("UPDATE tenants SET ativo = 0 WHERE id = ?", (tenant_id,))
    conn.commit()
    return {"ok": True, "message": "Usuário rejeitado"}


@router.get("/me")
def me(tenant: dict = Depends(require_tenant)):
    from shared.database import get_tenant_empresas

    empresas = get_tenant_empresas(tenant["id"])
    return {
        "id": tenant["id"],
        "nome_empresa": tenant["nome_empresa"],
        "email": tenant["email"],
        "plano": tenant["plano"],
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
