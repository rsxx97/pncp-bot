"""Registry de adapters por slug."""
from __future__ import annotations

from radar.adapters.base import PortalAdapter
from radar.adapters.comprasnet import ComprasnetAdapter
from radar.adapters.pncp import PncpAdapter
from radar.adapters._stubs import (
    BecSpAdapter,
    BllAdapter,
    ElicScAdapter,
    LicitacoesEAdapter,
    PortalComprasPublicasAdapter,
)

ADAPTER_REGISTRY: dict[str, type[PortalAdapter]] = {
    "pncp": PncpAdapter,
    "comprasnet": ComprasnetAdapter,
    "bll": BllAdapter,
    "bec_sp": BecSpAdapter,
    "licitacoes_e": LicitacoesEAdapter,
    "portal_compras_publicas": PortalComprasPublicasAdapter,
    "elicsc": ElicScAdapter,
}


def get_adapter(slug: str, credenciais: dict | None = None) -> PortalAdapter:
    cls = ADAPTER_REGISTRY.get(slug)
    if not cls:
        raise ValueError(f"Adapter desconhecido: {slug}")
    return cls(credenciais=credenciais)
