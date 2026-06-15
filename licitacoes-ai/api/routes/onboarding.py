"""Onboarding: o cliente diz o que a empresa faz → define campos + matching de editais."""
import json
import sys
from pathlib import Path
from fastapi import APIRouter, Depends
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.routes.auth import require_tenant

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# Tipos de negócio — cada um define quais campos de perfil mostrar e quais nichos casar
TIPOS_NEGOCIO = [
    {
        "key": "mao_obra",
        "label": "Mão de obra / Terceirização",
        "desc": "Você fornece pessoas: limpeza, vigilância, portaria, apoio administrativo.",
        "campos": "encargos",  # RAT/FAP/CPRB/regime (planilha IN 05/2017)
        "nichos": [
            {"key": "mdo_limpeza", "label": "Limpeza e conservação"},
            {"key": "seguranca", "label": "Vigilância e segurança"},
            {"key": "admin", "label": "Apoio administrativo / recepção"},
        ],
    },
    {
        "key": "obras",
        "label": "Obras / Engenharia",
        "desc": "Construção, reforma e manutenção predial.",
        "campos": "bdi",  # BDI + atestados de obra
        "nichos": [{"key": "obra", "label": "Obras e reforma"}],
    },
    {
        "key": "aquisicao",
        "label": "Aquisição / Fornecimento",
        "desc": "Você vende produtos: equipamentos, materiais, suprimentos.",
        "campos": "produtos",  # catálogo/fornecedores/margem (NÃO usa RAT/FAP)
        "nichos": [{"key": "aquisicao", "label": "Fornecimento de produtos"}],
    },
    {
        "key": "residuos",
        "label": "Resíduos / Ambiental",
        "desc": "Coleta, transporte e destinação de resíduos.",
        "campos": "encargos",
        "nichos": [{"key": "residuos", "label": "Resíduos"}],
    },
]


class ConfigRequest(BaseModel):
    tipo_negocio: str
    nichos: list[str] = []
    ufs: list[str] = []


@router.get("/opcoes")
def opcoes():
    """Tipos de negócio + nichos pra montar a tela de onboarding."""
    return {"tipos": TIPOS_NEGOCIO}


@router.get("/status")
def status(tenant: dict = Depends(require_tenant)):
    return {
        "onboarding_done": bool(tenant.get("onboarding_done", 0)),
        "tipo_negocio": tenant.get("tipo_negocio"),
        "nichos": json.loads(tenant.get("onboarding_nichos") or "[]"),
        "ufs": json.loads(tenant.get("onboarding_ufs") or "[]"),
    }


@router.post("/configurar")
def configurar(body: ConfigRequest, tenant: dict = Depends(require_tenant)):
    """Salva o perfil do cliente (tipo + nichos + UFs). Base pro matching de editais."""
    from shared.database import get_db

    tipos_validos = {t["key"] for t in TIPOS_NEGOCIO}
    if body.tipo_negocio not in tipos_validos:
        return {"ok": False, "erro": "tipo_negocio inválido"}

    conn = get_db()
    conn.execute(
        "UPDATE tenants SET tipo_negocio=?, onboarding_nichos=?, onboarding_ufs=?, onboarding_done=1 WHERE id=?",
        (body.tipo_negocio, json.dumps(body.nichos), json.dumps(body.ufs), tenant["id"]),
    )
    conn.commit()
    return {
        "ok": True,
        "tipo_negocio": body.tipo_negocio,
        "nichos": body.nichos,
        "ufs": body.ufs,
    }
