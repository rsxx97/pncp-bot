"""Cliente Claude API com retry, cost tracking e logging."""
import asyncio
import json
import logging
import time
from datetime import datetime

import anthropic

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_PRICING
from shared.database import registrar_execucao

log = logging.getLogger("llm_client")

# Rate limiter simples: máximo 5 chamadas por minuto
_call_timestamps: list[float] = []
_MAX_CALLS_PER_MIN = 5


def _rate_limit():
    """Espera se necessário para respeitar o rate limit."""
    now = time.time()
    # Remove timestamps com mais de 60 segundos
    while _call_timestamps and now - _call_timestamps[0] > 60:
        _call_timestamps.pop(0)
    if len(_call_timestamps) >= _MAX_CALLS_PER_MIN:
        wait = 60 - (now - _call_timestamps[0])
        if wait > 0:
            log.info(f"Rate limit: aguardando {wait:.1f}s")
            time.sleep(wait)
    _call_timestamps.append(time.time())


def _calc_cost(input_tokens: int, output_tokens: int) -> float:
    """Calcula custo em USD."""
    return (
        input_tokens * CLAUDE_PRICING["input_per_mtok"] / 1_000_000
        + output_tokens * CLAUDE_PRICING["output_per_mtok"] / 1_000_000
    )


def _get_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY não configurada. Defina no .env")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def ask_claude(
    system: str,
    user: str,
    max_tokens: int = 4096,
    agente: str = "geral",
    pncp_id: str | None = None,
) -> str:
    """Chamada síncrona ao Claude. Retorna texto da resposta."""
    _rate_limit()
    client = _get_client()
    start = time.time()

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )

            duracao = time.time() - start
            input_tok = response.usage.input_tokens
            output_tok = response.usage.output_tokens
            custo = _calc_cost(input_tok, output_tok)
            total_tok = input_tok + output_tok

            log.info(
                f"Claude [{agente}]: {input_tok}+{output_tok} tokens, "
                f"${custo:.4f}, {duracao:.1f}s"
            )

            registrar_execucao(
                agente=agente,
                pncp_id=pncp_id,
                status="sucesso",
                duracao_seg=duracao,
                tokens_usados=total_tok,
                custo_estimado=custo,
            )

            return response.content[0].text

        except anthropic.RateLimitError:
            wait = 2 ** (attempt + 1)
            log.warning(f"Rate limit (tentativa {attempt+1}/3). Aguardando {wait}s...")
            time.sleep(wait)
        except anthropic.APIError as e:
            wait = 2 ** (attempt + 1)
            log.error(f"API error (tentativa {attempt+1}/3): {e}")
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

    raise RuntimeError("Falha após 3 tentativas")


def ask_claude_json(
    system: str,
    user: str,
    max_tokens: int = 2048,
    agente: str = "geral",
    pncp_id: str | None = None,
) -> dict:
    """Chamada ao Claude que espera resposta JSON. Faz parse e retry se inválido."""
    for attempt in range(2):
        text = ask_claude(
            system=system,
            user=user,
            max_tokens=max_tokens,
            agente=agente,
            pncp_id=pncp_id,
        )

        # Tenta extrair JSON do texto (pode ter markdown ```json ... ```)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # Remove markdown code block
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt == 0:
                log.warning("JSON inválido na resposta. Retentando com prompt mais explícito...")
                system += "\n\nIMPORTANTE: Retorne SOMENTE JSON válido. Sem texto antes ou depois. Sem markdown."
            else:
                log.error(f"JSON inválido após 2 tentativas. Resposta: {text[:200]}")
                raise ValueError(f"Claude retornou JSON inválido: {text[:200]}")


# ── Versões async (para uso com FastAPI/Telegram) ──────────────────────

async def ask_claude_async(
    system: str,
    user: str,
    max_tokens: int = 4096,
    agente: str = "geral",
    pncp_id: str | None = None,
) -> str:
    """Versão async — roda a chamada síncrona em thread."""
    return await asyncio.to_thread(
        ask_claude, system, user, max_tokens, agente, pncp_id
    )


async def ask_claude_json_async(
    system: str,
    user: str,
    max_tokens: int = 2048,
    agente: str = "geral",
    pncp_id: str | None = None,
) -> dict:
    """Versão async — roda a chamada síncrona em thread."""
    return await asyncio.to_thread(
        ask_claude_json, system, user, max_tokens, agente, pncp_id
    )
