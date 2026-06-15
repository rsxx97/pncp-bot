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
    """Sempre usa Gemini (grátis). Claude foi desativado por ser pago."""
    return bool(_get_gemini_key())


def _claude_disabled():
    raise RuntimeError(
        "Claude API está DESATIVADA por decisão de produto (custo zero). "
        "Use Gemini grátis (GEMINI_API_KEY) ou refatore pro código puro "
        "(regex/motor_matematico)."
    )


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
    """DESATIVADO — Claude é pago. Use Gemini grátis ou código puro."""
    _claude_disabled()
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

    if not _use_gemini():
        raise RuntimeError(
            "GEMINI_API_KEY não configurada. Sistema usa apenas Gemini grátis + código puro. "
            "Claude foi desativado por ser pago."
        )

    for attempt in range(3):
        try:
            text = _ask_gemini(system, user, max_tokens)
            duracao = time.time() - start
            log.info(f"gemini [{agente}]: {duracao:.1f}s (grátis)")

            registrar_execucao(
                agente=agente,
                pncp_id=pncp_id,
                status="sucesso",
                duracao_seg=duracao,
                tokens_usados=0,
                custo_estimado=0.0,
            )
            return text

        except Exception as e:
            wait = 2 ** (attempt + 1)
            log.warning(f"gemini erro (tentativa {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(wait)
            else:
                registrar_execucao(
                    agente=agente,
                    pncp_id=pncp_id,
                    status="erro",
                    duracao_seg=time.time() - start,
                    erro_msg=str(e),
                )
                raise

    raise RuntimeError("Falha Gemini após 3 tentativas")


def ask_claude_json(
    system: str,
    user: str,
    max_tokens: int = 2048,
    agente: str = "geral",
    pncp_id: str | None = None,
    fallback_on_quota: bool = True,
) -> dict:
    """Chamada ao LLM que espera resposta JSON.

    Se Gemini retornar quota 429 e fallback_on_quota=True, retorna
    {"_needs_manual_review": True, "_reason": "..."} em vez de crashar.
    O pipeline segue funcionando; o dashboard mostra "precisa revisão".
    """
    for attempt in range(2):
        try:
            text = ask_claude(
                system=system,
                user=user,
                max_tokens=max_tokens,
                agente=agente,
                pncp_id=pncp_id,
            )
        except Exception as e:
            # Gemini quota 429, API desativada, timeout — graceful degradation
            msg = str(e).lower()
            is_quota = any(x in msg for x in ["429", "quota", "desativada", "rate limit", "exceeded"])
            if fallback_on_quota and is_quota:
                log.warning(f"Gemini indisponivel [{agente}]: marcando edital para revisao manual")
                return {
                    "_needs_manual_review": True,
                    "_reason": f"Gemini indisponivel: {str(e)[:100]}",
                    "_agente": agente,
                    "_pncp_id": pncp_id,
                }
            raise

        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt == 0:
                log.warning("JSON invalido. Retentando...")
                system += "\n\nIMPORTANTE: Retorne SOMENTE JSON valido."
            else:
                log.error(f"JSON invalido apos 2 tentativas: {text[:200]}")
                return {
                    "_needs_manual_review": True,
                    "_reason": f"LLM retornou JSON invalido: {text[:100]}",
                    "_agente": agente,
                    "_pncp_id": pncp_id,
                }

    # fim da funcao


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
