"""Rota de chat com Claude — assistente de licitações."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path

router = APIRouter(prefix="/api/chat", tags=["chat"])

SYSTEM_PROMPT = """Você é o assistente de licitações do sistema Licitações AI.
Você ajuda empresas de terceirização (limpeza, segurança, facilities, apoio administrativo)
a entender e participar de licitações públicas no Brasil.

Você pode ajudar com:
- Dúvidas sobre editais, modalidades (pregão, concorrência, dispensa)
- Explicar requisitos de habilitação e qualificação técnica
- Esclarecer sobre planilha de custos IN 05/2017
- Encargos trabalhistas, BDI, tributos
- CCTs e pisos salariais
- Estratégias competitivas para licitações
- Regime tributário (lucro real vs presumido, desoneração)

Seja direto e prático. Responda em português. Use linguagem simples."""


class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role": "user"|"assistant", "content": "..."}]
    context: str | None = None  # Contexto opcional (dados do edital aberto)


@router.post("")
def chat(body: ChatRequest):
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL
    import anthropic

    key = ANTHROPIC_API_KEY
    if not key:
        import os
        key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(500, "API key não configurada")

    system = SYSTEM_PROMPT
    if body.context:
        system += f"\n\nContexto do edital aberto:\n{body.context}"

    # Limita histórico a últimas 10 mensagens para economizar tokens
    messages = body.messages[-10:]

    try:
        client = anthropic.Anthropic(api_key=key)

        def generate():
            with client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=system,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        raise HTTPException(500, f"Erro no chat: {str(e)}")
