"""Stubs dos adapters que ainda não foram implementados.

Cada stub levanta NotImplementedError com mensagem clara — UI mostra portal
como "em breve" e impede o worker de pollar.

Pra implementar:
  1. Substitua a classe stub aqui ou crie radar/adapters/<slug>.py
  2. Implemente autenticar() + fetch_pregao()
  3. Atualize registry.py
"""
from __future__ import annotations

from radar.adapters.base import PortalAdapter, PregaoSnapshot


class _StubAdapter(PortalAdapter):
    requer_credencial = True

    async def fetch_pregao(self, identificador: str) -> PregaoSnapshot:
        raise NotImplementedError(
            f"Adapter '{self.slug}' ainda não implementado. "
            f"Cadastre o pregão no PNCP por enquanto."
        )


class BllAdapter(_StubAdapter):
    slug = "bll"
    nome = "BLL Compras"


class BecSpAdapter(_StubAdapter):
    slug = "bec_sp"
    nome = "BEC-SP"


class LicitacoesEAdapter(_StubAdapter):
    slug = "licitacoes_e"
    nome = "Licitações-e (BB)"
    # TODO: scraping com captcha — reusar ddddocr do bot_sistema_s


class PortalComprasPublicasAdapter(_StubAdapter):
    slug = "portal_compras_publicas"
    nome = "Portal de Compras Públicas"


class ElicScAdapter(_StubAdapter):
    slug = "elicsc"
    nome = "eLicSC (SC)"
