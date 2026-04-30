"""Listener Telegram do bot OBRA (NichoBot @k1RossiBot).

Escuta cliques no botão "📄 Baixar Edital" — quando o usuário clica, é
redirecionado pra DM com o bot via deep link `t.me/<bot>?start=ed_<pncp_id>`.
Este listener captura o /start, baixa os arquivos do PNCP via API e envia
como documentos na DM do usuário.

Uso:
    python core/skills/listener_obra.py

Pra rodar 24/7: configurar Task Scheduler com /loop ou daemon.
"""
import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("listener_obra")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_OBRA")
OFFSET_FILE = Path(__file__).parent.parent.parent / "data" / "telegram_offset_obra.json"
OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return json.loads(OFFSET_FILE.read_text()).get("offset", 0)
        except Exception:
            return 0
    return 0


def _save_offset(offset: int):
    OFFSET_FILE.write_text(json.dumps({"offset": offset}))


def get_updates(offset: int = 0, timeout: int = 25) -> list:
    try:
        r = httpx.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": timeout},
            timeout=timeout + 5,
        )
        if r.status_code == 200:
            return r.json().get("result", [])
    except httpx.TimeoutException:
        pass
    except Exception as e:
        log.warning(f"getUpdates erro: {e}")
    return []


def send_message(chat_id: int, texto: str):
    try:
        httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": texto, "disable_web_page_preview": True},
            timeout=20,
        )
    except Exception as e:
        log.warning(f"send_message: {e}")


def send_document_url(chat_id: int, file_url: str, filename: str, caption: str = ""):
    """Baixa de file_url e envia como documento."""
    try:
        with httpx.stream("GET", file_url, timeout=60, follow_redirects=True) as r:
            if r.status_code != 200:
                log.warning(f"download {file_url} status {r.status_code}")
                return False
            content = r.read()
        files = {"document": (filename, content, "application/pdf")}
        data = {"chat_id": str(chat_id), "caption": caption[:1024]}
        rr = httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
            data=data, files=files, timeout=120,
        )
        if rr.status_code == 200:
            return True
        log.warning(f"sendDocument {rr.status_code}: {rr.text[:200]}")
    except Exception as e:
        log.warning(f"send_document_url: {e}")
    return False


def baixar_e_enviar_arquivos(chat_id: int, pncp_id: str):
    """pncp_id formato: <cnpj>-<ano>-<seq>. Busca arquivos no PNCP e envia."""
    try:
        cnpj, ano, seq = pncp_id.split("-")
    except ValueError:
        send_message(chat_id, f"⚠️ ID inválido: {pncp_id}")
        return

    api = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"
    try:
        r = httpx.get(api, timeout=30)
        if r.status_code != 200:
            send_message(chat_id, f"⚠️ PNCP retornou {r.status_code} — edital pode não estar disponível.")
            return
        arquivos = r.json()
    except Exception as e:
        send_message(chat_id, f"⚠️ Erro consultando PNCP: {e}")
        return

    if not arquivos:
        send_message(chat_id, "⚠️ Nenhum arquivo disponível para este edital ainda.")
        return

    send_message(chat_id, f"🔍 Encontrados {len(arquivos)} arquivo(s). Enviando…")

    enviados = 0
    for i, arq in enumerate(arquivos, 1):
        url = arq.get("url") or arq.get("uri")
        titulo = arq.get("titulo") or f"arquivo_{i}.pdf"
        tipo = arq.get("tipoDocumentoNome") or ""
        caption = f"📄 {tipo}\n{titulo[:200]}\nEdital: {pncp_id}"
        if url and send_document_url(chat_id, url, titulo, caption):
            enviados += 1
        time.sleep(0.5)

    if enviados == 0:
        send_message(chat_id, "⚠️ Falhou em todos os arquivos.")
    elif enviados < len(arquivos):
        send_message(chat_id, f"⚠️ {enviados}/{len(arquivos)} arquivos enviados (alguns falharam).")


def process_message(msg: dict):
    """Processa mensagem privada. Captura /start <payload>."""
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    chat_type = chat.get("type")
    text = (msg.get("text") or "").strip()

    # Só processa privado (DM)
    if chat_type != "private":
        return

    if text.startswith("/start"):
        partes = text.split(maxsplit=1)
        payload = partes[1] if len(partes) > 1 else ""
        if payload.startswith("ed_"):
            pncp_id = payload[3:]
            log.info(f"DM /start ed_{pncp_id} de chat {chat_id}")
            send_message(chat_id, f"📥 Buscando arquivos do edital {pncp_id}…")
            baixar_e_enviar_arquivos(chat_id, pncp_id)
        else:
            send_message(chat_id, "👋 Olá! Clique em '📄 Baixar Edital' nas mensagens do canal pra receber os arquivos aqui.")


def main():
    if not BOT_TOKEN:
        print("ERRO: TELEGRAM_BOT_TOKEN_OBRA não configurado.")
        sys.exit(1)

    print(f"🔊 Listener OBRA iniciado | bot ...{BOT_TOKEN[-6:]}")
    print("   Aguardando cliques no botão 📄 Baixar Edital (deep link DM)")
    offset = _load_offset()

    while True:
        try:
            updates = get_updates(offset)
            for upd in updates:
                uid = upd.get("update_id")
                if uid is not None:
                    offset = uid + 1
                    _save_offset(offset)
                if "message" in upd:
                    process_message(upd["message"])
        except KeyboardInterrupt:
            print("\nParando listener…")
            break
        except Exception as e:
            log.error(f"loop: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
