"""Cliente LLM com suporte a Gemini (gratuito) e Claude (fallback)."""
import asyncio
import json
import logging
import time
import os
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.database import registrar_execucao

log = logging.getLogger("llm_client")

# Rate limiter: max 14 chamadas por minuto (Gemini free = 15/min)
_call_timestamps: list[float] = []
_MAX_CALLS_PER_MIN = 14


def _rate_limit():
    now = time.time()
    while _call_timestamps and now - _call_timestamps[0] > 60:
        _call_timestamps.pop(0)
    if len(_call_timestamps) >= _MAX_CALLS_PER_MIN:
        wait = 60 - (now - _call_timestamps[0])
        if wait > 0:
            log.info(f"Rate limit: aguardando {wait:.1f}s")
            time.sleep(wait)
    _call_timestamps.append(time.time())


def _get_gemini_key():
    from config.settings import GEMINI_API_KEY
    return GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")


def _get_anthropic_key():
    from config.settings import ANTHROPIC_API_KEY
    return ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")


def _use_gemini():
    """Retorna True se Gemini está configurado e disponível.
    Desabilitado temporariamente - quota esgotada."""
    return False  # TODO: reabilitar quando tiver nova API key


def _ask_gemini(system: str, user: str, max_tokens: int = 4096) -> str:
    """Chamada ao Gemini Flash (gratuito)."""
    import google.generativeai as genai

    key = _get_gemini_key()
    genai.configure(api_key=key)

    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        system_instruction=system,
    )

    response = model.generate_content(
        user,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.1,
        ),
    )

    return response.text


def _ask_claude(system: str, user: str, max_tokens: int = 4096) -> str:
    """Chamada ao Claude (fallback pago)."""
    import anthropic
    from config.settings import CLAUDE_MODEL

    key = _get_anthropic_key()
    if not key:
        raise ValueError("Nenhuma API key configurada (GEMINI_API_KEY ou ANTHROPIC_API_KEY)")

    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    return response.content[0].text


def ask_claude(
    system: str,
    user: str,
    max_tokens: int = 4096,
    agente: str = "geral",
    pncp_id: str | None = None,
) -> str:
    """Chamada ao LLM. Usa Gemini Flash (grátis) se disponível, senão Claude."""
    _rate_limit()
    start = time.time()
    provider = "gemini" if _use_gemini() else "claude"

    for attempt in range(3):
        try:
            if provider == "gemini":
                text = _ask_gemini(system, user, max_tokens)
            else:
                text = _ask_claude(system, user, max_tokens)

            duracao = time.time() - start
            custo = 0.0 if provider == "gemini" else 0.05  # estimativa

            log.info(f"{provider} [{agente}]: {duracao:.1f}s, ${custo:.4f}")

            registrar_execucao(
                agente=agente,
                pncp_id=pncp_id,
                status="sucesso",
                duracao_seg=duracao,
                tokens_usados=0,
                custo_estimado=custo,
            )

            return text

        except Exception as e:
            wait = 2 ** (attempt + 1)
            log.warning(f"{provider} erro (tentativa {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(wait)
                # Se Gemini falhou, tenta Claude como fallback
                if provider == "gemini" and _get_anthropic_key():
                    log.info("Fallback para Claude...")
                    provider = "claude"
            else:
                registrar_execucao(
                    agente=agente,
                    pncp_id=pncp_id,
                    status="erro",
                    duracao_seg=time.time() - start,
                    erro_msg=str(e),
                )
                raise

    raise RuntimeError("Falha após 3 tentativas")


def ask_claude_json(
    system: str,
    user: str,
    max_tokens: int = 2048,
    agente: str = "geral",
    pncp_id: str | None = None,
) -> dict:
    """Chamada ao LLM que espera resposta JSON."""
    for attempt in range(2):
        text = ask_claude(
            system=system,
            user=user,
            max_tokens=max_tokens,
            agente=agente,
            pncp_id=pncp_id,
        )

        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt == 0:
                log.warning("JSON inválido. Retentando...")
                system += "\n\nIMPORTANTE: Retorne SOMENTE JSON válido. Sem texto antes ou depois."
            else:
                log.error(f"JSON inválido após 2 tentativas: {text[:200]}")
                raise ValueError(f"LLM retornou JSON inválido: {text[:200]}")


# ── Versões async ──────────────────────

async def ask_claude_async(
    system: str, user: str, max_tokens: int = 4096,
    agente: str = "geral", pncp_id: str | None = None,
) -> str:
    return await asyncio.to_thread(ask_claude, system, user, max_tokens, agente, pncp_id)


async def ask_claude_json_async(
    system: str, user: str, max_tokens: int = 2048,
    agente: str = "geral", pncp_id: str | None = None,
) -> dict:
    return await asyncio.to_thread(ask_claude_json, system, user, max_tokens, agente, pncp_id)
