"""Kill-switch global do 2captcha — quando a API retorna ERROR_ZERO_BALANCE
(saldo esgotado), desativamos chamadas ao 2captcha por 24h pra parar o loop
de gastar Playwright + Chrome + tempo de processo num solver que nunca vai
funcionar até alguém recarregar.

Compartilhado por comprasnet_chat.py e comprasnet_pfx.py.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("radar.captcha_state")

_DESATIVADO_ATE: float = 0.0  # time.monotonic() quando re-habilita
_DURACAO_SEG = 86400  # 24h


def desativar_por_saldo_zero(detalhe: str = "") -> None:
    """Marca 2captcha indisponível por 24h. Idempotente."""
    global _DESATIVADO_ATE
    novo = time.monotonic() + _DURACAO_SEG
    if novo > _DESATIVADO_ATE:
        _DESATIVADO_ATE = novo
        log.error(f"2captcha DESATIVADO por {_DURACAO_SEG/3600:.0f}h (saldo zero). {detalhe}")


def ativo() -> bool:
    """True se 2captcha pode ser chamado agora."""
    return time.monotonic() >= _DESATIVADO_ATE


def reativar() -> None:
    """Resets a flag — pra ser chamado quando saldo for recarregado."""
    global _DESATIVADO_ATE
    _DESATIVADO_ATE = 0.0


def eh_erro_saldo_zero(erro: Exception | str) -> bool:
    """Detecta se o erro é falta de saldo no 2captcha."""
    msg = str(erro).upper()
    return "ZERO_BALANCE" in msg or "NO_BALANCE" in msg or "INSUFFICIENT" in msg
