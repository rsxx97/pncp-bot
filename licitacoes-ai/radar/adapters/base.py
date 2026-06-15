"""Contrato base dos adaptadores de portal de licitação.

Pra adicionar um portal novo:
  1. Cria arquivo radar/adapters/<slug>.py com classe que herda PortalAdapter
  2. Implementa autenticar(), fetch_pregao() (mínimo)
  3. Registra em radar/adapters/registry.py
  4. Adiciona seed em shared/database.py _PORTAIS_SEED (slug, nome, base_url, tipo)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ── Erros ─────────────────────────────────────────────────────────────

class PortalError(Exception):
    """Base de erros de portal."""


class AuthError(PortalError):
    """Credenciais inválidas, expiradas ou sem permissão."""


class CaptchaError(PortalError):
    """Portal apresentou captcha que precisa de intervenção humana."""


class RateLimitError(PortalError):
    """Portal sinalizou rate limit. Retry após `retry_em` segundos."""

    def __init__(self, mensagem: str = "rate limit", retry_em: float = 30.0):
        super().__init__(mensagem)
        self.retry_em = retry_em


class NotFoundError(PortalError):
    """Pregão não existe (ou foi removido) no portal."""


# ── Snapshot ──────────────────────────────────────────────────────────

@dataclass
class PregaoSnapshot:
    portal_slug: str
    identificador: str               # ID nativo do portal (CNPJ-ANO-SEQ no PNCP, UASG+nº no ComprasNet, etc)
    numero: str | None = None
    orgao: str | None = None
    objeto: str | None = None
    data_abertura: datetime | None = None
    data_encerramento: datetime | None = None
    status: str = "agendado"         # agendado | em_sessao | suspenso | encerrado | fracassado | deserto
    fase: str | None = None          # propostas | lances | negociacao | habilitacao | adjudicacao | homologacao
    valor_estimado: float | None = None
    melhor_lance: float | None = None
    melhor_lance_cnpj: str | None = None
    minha_posicao: int | None = None
    meu_melhor_lance: float | None = None
    mensagens: list[dict] = field(default_factory=list)
    lances: list[dict] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "portal_slug": self.portal_slug,
            "identificador": self.identificador,
            "numero": self.numero,
            "orgao": self.orgao,
            "objeto": self.objeto,
            "data_abertura": self.data_abertura.isoformat() if self.data_abertura else None,
            "data_encerramento": self.data_encerramento.isoformat() if self.data_encerramento else None,
            "status": self.status,
            "fase": self.fase,
            "valor_estimado": self.valor_estimado,
            "melhor_lance": self.melhor_lance,
            "melhor_lance_cnpj": self.melhor_lance_cnpj,
            "minha_posicao": self.minha_posicao,
            "meu_melhor_lance": self.meu_melhor_lance,
            "mensagens": self.mensagens,
            "lances": self.lances,
            "fetched_at": self.fetched_at.isoformat(),
        }


# ── Adapter ───────────────────────────────────────────────────────────

class PortalAdapter(ABC):
    """Strategy: 1 adapter por portal. Stateful (mantém sessão HTTP/cookies)."""

    slug: str = ""           # override: "pncp", "comprasnet", ...
    nome: str = ""
    requer_credencial: bool = False
    suporta_lances_proprios: bool = False  # True se o adapter sabe identificar lances do CNPJ logado

    def __init__(self, credenciais: dict | None = None):
        self.credenciais = credenciais or {}
        self._autenticado = False

    @abstractmethod
    async def fetch_pregao(self, identificador: str) -> PregaoSnapshot:
        """Snapshot atual. Levanta NotFoundError, AuthError, RateLimitError, CaptchaError."""

    async def autenticar(self) -> bool:
        """Autentica com self.credenciais. Default: sem auth (API pública)."""
        self._autenticado = True
        return True

    async def fetch_mensagens(self, identificador: str, desde: datetime | None = None) -> list[dict]:
        return []

    async def fetch_lances(self, identificador: str, desde: datetime | None = None) -> list[dict]:
        return []

    async def encerrar(self) -> None:
        self._autenticado = False
