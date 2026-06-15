"""Token bucket por portal — proteção contra ban."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class TokenBucket:
    def __init__(self, capacidade: float, refill_por_seg: float):
        self.capacidade = capacidade
        self.refill = refill_por_seg
        self.tokens = capacidade
        self.last = time.monotonic()

    async def adquirir(self, n: float = 1.0):
        while True:
            agora = time.monotonic()
            self.tokens = min(self.capacidade, self.tokens + (agora - self.last) * self.refill)
            self.last = agora
            if self.tokens >= n:
                self.tokens -= n
                return
            espera = (n - self.tokens) / self.refill
            await asyncio.sleep(max(0.05, espera))


_BUCKETS: dict[str, TokenBucket] = defaultdict(lambda: TokenBucket(capacidade=5, refill_por_seg=1.0))

# Overrides por portal — scraping conservador
_BUCKETS["comprasnet"] = TokenBucket(capacidade=2, refill_por_seg=0.33)
_BUCKETS["bll"] = TokenBucket(capacidade=2, refill_por_seg=0.33)
_BUCKETS["bec_sp"] = TokenBucket(capacidade=2, refill_por_seg=0.33)
_BUCKETS["licitacoes_e"] = TokenBucket(capacidade=2, refill_por_seg=0.33)
_BUCKETS["portal_compras_publicas"] = TokenBucket(capacidade=2, refill_por_seg=0.33)
_BUCKETS["elicsc"] = TokenBucket(capacidade=2, refill_por_seg=0.33)


async def aguardar_token(portal_slug: str):
    await _BUCKETS[portal_slug].adquirir()
