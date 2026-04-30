"""Bot Manutec — radar de editais de MANUTENÇÃO PREDIAL.

Cliente: Manutec
Foco: manutenção predial (eletricista, HVAC, elétrica, hidráulica)
UF: RJ (principalmente)
Nicho: obra (mesma CCT SINTEIC, modelo BDI)

Canal: TELEGRAM_BOT_TOKEN_MANUTEC no .env

Dedup: data/manutec_sent.json
"""
import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import httpx

LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)

from config.settings import DB_PATH
from shared.nichos import formatar_edital as _formatar_canonico

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_manutec")

SENT_FILE = Path(__file__).parent / "data" / "manutec_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_OBRA") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_OBRA") or os.getenv("TELEGRAM_CHAT_ID")

UFS_MANUTEC = ["RJ"]

# Keywords específicas de manutenção predial (subconjunto de obra)
KEYWORDS_MANUTENCAO = [
    "manutenção predial", "manutencao predial",
    "manutenção preventiva", "manutencao preventiva",
    "manutenção corretiva", "manutencao corretiva",
    "manutenção elétrica", "manutencao eletrica",
    "manutenção hidráulica", "manutencao hidraulica",
    "ar condicionado", "climatização", "climatizacao",
    "HVAC", "elevador", "instalações prediais",
    "serviços de engenharia", "servicos de engenharia",
]

MODALIDADES_ACEITAS = (
    "Pregão Eletrônico", "Pregão Presencial",
    "Concorrência", "Tomada de Preços", "Convite",
    "Dispensa", "Dispensa de Licitação",  # com aviso
)
MODALIDADES_CONTRATACAO_DIRETA = (
    "Dispensa", "Dispensa de Licitação",
    "Inexigibilidade", "Inexigibilidade de Licitação",
)


def _load_sent() -> set:
    if SENT_FILE.exists():
        return set(json.loads(SENT_FILE.read_text(encoding="utf-8")))
    return set()


def _save_sent(s: set):
    SENT_FILE.write_text(json.dumps(sorted(s)), encoding="utf-8")


def _fmt_brl(v):
    if v is None or v == 0:
        return "—"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _eh_manutencao(objeto: str) -> bool:
    """Verifica se é manutenção predial (subnicho de obra)."""
    obj = (objeto or "").lower()
    return any(k in obj for k in KEYWORDS_MANUTENCAO)


def enviar_telegram(mensagem: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        log.warning("TELEGRAM_BOT_TOKEN_MANUTEC não configurado")
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = httpx.post(url, json={
            "chat_id": CHAT_ID,
            "text": mensagem,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=20)
        return r.status_code == 200
    except Exception as e:
        log.warning(f"Telegram: {e}")
        return False


def formatar_edital(edital: dict) -> str:
    """Cabecalho MANUTEC + corpo canônico (igual Miami/SL)."""
    return "🔧 MANUTEC — MANUTENÇÃO PREDIAL\n\n" + _formatar_canonico(edital)


def executar() -> dict:
    stats = {"encontrados": 0, "enviados": 0, "ja_enviados": 0, "falhas": 0, "nao_manutencao": 0}
    sent = _load_sent()
    agora = datetime.now().isoformat()

    placeholders = ",".join("?" for _ in UFS_MANUTEC)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(f"""
        SELECT * FROM editais
        WHERE uf IN ({placeholders})
          AND nicho = 'obra'
          AND (data_encerramento IS NULL OR data_encerramento > ?)
        ORDER BY data_publicacao DESC
        LIMIT 200
    """, (*UFS_MANUTEC, agora)).fetchall()

    for r in rows:
        pncp_id = r["pncp_id"]
        # Filtra só manutenção predial (subconjunto de obra)
        if not _eh_manutencao(r["objeto"]):
            stats["nao_manutencao"] += 1
            continue
        stats["encontrados"] += 1

        if pncp_id in sent:
            stats["ja_enviados"] += 1
            continue

        modal = r["modalidade"] or ""
        if not any(m.lower() in modal.lower() for m in MODALIDADES_ACEITAS):
            continue

        msg = formatar_edital(dict(r))
        if any(m in modal for m in MODALIDADES_CONTRATACAO_DIRETA):
            msg = "⚠️ CONTRATAÇÃO DIRETA — verifique se é cotação aberta\n\n" + msg
        if enviar_telegram(msg):
            sent.add(pncp_id)
            stats["enviados"] += 1
            log.info(f"Enviado: {pncp_id}")
        else:
            stats["falhas"] += 1

    _save_sent(sent)
    conn.close()

    log.info(f"Manutec: {json.dumps(stats, ensure_ascii=False)}")
    return stats


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    executar()
