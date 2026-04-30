"""Bot B7 Soluções — radar de editais de CONSTRUÇÃO, REFORMA E MANUTENÇÃO PREDIAL.

Cliente: B7 Soluções (SC/RJ)
Nicho: obra (construção + reforma + manutenção predial)
Usa formato CANÔNICO (shared/nichos.py) igual Miami/SL.

Dedup: data/b7_obras_sent.json
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
from shared.nichos import formatar_edital

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_b7_obras")

SENT_FILE = Path(__file__).parent / "data" / "b7_obras_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_OBRA") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_OBRA") or os.getenv("TELEGRAM_CHAT_ID")

UFS_B7 = ["SC", "RJ"]

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


def enviar_telegram(texto: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        log.warning("TELEGRAM_BOT_TOKEN_B7 / TELEGRAM_CHAT_B7 nao configurado")
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": texto, "disable_web_page_preview": True},
            timeout=20,
        )
        if r.status_code != 200:
            log.warning(f"Telegram {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        log.warning(f"Telegram falha: {e}")
        return False


def executar() -> dict:
    """Dispara editais novos de obra pra B7 usando formato canônico."""
    stats = {"encontrados": 0, "enviados": 0, "ja_enviados": 0, "falhas": 0}
    sent = _load_sent()
    agora = datetime.now().isoformat()

    placeholders = ",".join("?" for _ in UFS_B7)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(f"""
        SELECT * FROM editais
        WHERE uf IN ({placeholders})
          AND nicho = 'obra'
          AND (data_encerramento IS NULL OR data_encerramento > ?)
        ORDER BY data_publicacao DESC
        LIMIT 50
    """, (*UFS_B7, agora)).fetchall()

    stats["encontrados"] = len(rows)

    for r in rows:
        pncp_id = r["pncp_id"]
        if pncp_id in sent:
            stats["ja_enviados"] += 1
            continue

        modal = r["modalidade"] or ""
        if not any(m.lower() in modal.lower() for m in MODALIDADES_ACEITAS):
            continue

        header = "🏗 B7 SOLUÇÕES — OBRA/REFORMA\n\n"
        if any(m in modal for m in MODALIDADES_CONTRATACAO_DIRETA):
            header = "⚠️ CONTRATAÇÃO DIRETA — verifique se é cotação aberta\n\n" + header
        msg = header + formatar_edital(dict(r))

        if enviar_telegram(msg):
            sent.add(pncp_id)
            stats["enviados"] += 1
            log.info(f"Enviado B7: {pncp_id}")
        else:
            stats["falhas"] += 1

    _save_sent(sent)
    conn.close()

    log.info(f"Bot B7 Obras: {json.dumps(stats, ensure_ascii=False)}")
    return stats


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="So imprime, nao envia")
    args = ap.parse_args()

    if args.dry_run:
        # Imprime no console o que seria enviado
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in UFS_B7)
        agora = datetime.now().isoformat()
        rows = conn.execute(f"""
            SELECT * FROM editais WHERE uf IN ({placeholders}) AND nicho='obra'
              AND (data_encerramento IS NULL OR data_encerramento > ?)
            ORDER BY data_publicacao DESC LIMIT 3
        """, (*UFS_B7, agora)).fetchall()
        for r in rows:
            print("\n" + "="*70)
            print("🏗 B7 SOLUÇÕES — OBRA/REFORMA\n")
            print(formatar_edital(dict(r)))
        conn.close()
    else:
        executar()
