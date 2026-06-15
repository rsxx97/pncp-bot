"""Cifra/decifra credenciais de portais com Fernet (AES-128-CBC + HMAC-SHA256).

Chave: env var RADAR_FERNET_KEY (32 bytes base64). Gere com:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import base64
import json
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("radar.credenciais")


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = os.environ.get("RADAR_FERNET_KEY")
    if not key:
        # Dev fallback determinístico — NUNCA usar em produção
        seed = os.environ.get("JWT_SECRET", "dev-radar")
        key = base64.urlsafe_b64encode(seed.encode("utf-8").ljust(32, b"0")[:32]).decode()
        log.warning("RADAR_FERNET_KEY não configurada; usando fallback dev (NÃO seguro pra produção).")
    return Fernet(key.encode() if isinstance(key, str) else key)


def cifrar(valor: str | None) -> str | None:
    if valor is None or valor == "":
        return None
    return _fernet().encrypt(valor.encode("utf-8")).decode("utf-8")


def decifrar(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        log.error("Falha ao decifrar token (chave inválida ou rotacionada).")
        return None


def cifrar_dict(d: dict | None) -> str | None:
    if not d:
        return None
    return cifrar(json.dumps(d, ensure_ascii=False))


def decifrar_dict(token: str | None) -> dict | None:
    plain = decifrar(token)
    if not plain:
        return None
    try:
        return json.loads(plain)
    except json.JSONDecodeError:
        return None


def cifrar_bytes(data: bytes | None) -> str | None:
    """Cifra bytes brutos (ex: .pfx). Retorna token Fernet em base64 ASCII."""
    if not data:
        return None
    return _fernet().encrypt(data).decode("utf-8")


def decifrar_bytes(token: str | None) -> bytes | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("utf-8"))
    except InvalidToken:
        log.error("Falha ao decifrar bytes (chave Fernet inválida ou rotacionada).")
        return None
