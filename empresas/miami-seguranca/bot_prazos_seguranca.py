"""Bot de prazos — monitora abertura/encerramento de editais de SEGURANCA RJ.

Janelas: 48h, 24h, 2h antes. Zero API.
Envia alertas no canal MIAMI VIGILANCIA E SEGURANCA.
"""
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)

from config.settings import DB_PATH
from shared.nichos import detectar_nicho

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_prazos_seguranca")

SENT_FILE = Path(__file__).parent / "data" / "prazos_seguranca_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_SEGURANCA")
CHAT_ID = os.getenv("TELEGRAM_CHAT_SEGURANCA")

JANELAS_HORAS = [48, 24, 2]


def _load_sent() -> set:
    if SENT_FILE.exists():
        return set(json.loads(SENT_FILE.read_text(encoding="utf-8")))
    return set()


def _save_sent(s: set):
    SENT_FILE.write_text(json.dumps(sorted(s)), encoding="utf-8")


def _parse_data(s: str):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except Exception:
            continue
    return None


def _fmt_brl(v):
    try:
        v = float(v)
        inteiro = int(v)
        centavos = round((v - inteiro) * 100)
        s = f"{inteiro:,}".replace(",", ".")
        return f"{s},{centavos:02d}"
    except Exception:
        return f"{v}"


def _send_telegram(msg: str) -> bool:
    if not (BOT_TOKEN and CHAT_ID):
        log.warning(f"SEM TELEGRAM CONFIG: {msg}")
        return False
    try:
        import httpx
        r = httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=15,
        )
        return r.status_code == 200
    except Exception as e:
        log.error(f"Telegram erro: {e}")
        return False


def verificar_prazos() -> dict:
    sent = _load_sent()
    stats = {"verificados": 0, "alertas_enviados": 0}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT pncp_id, orgao_nome, objeto, data_abertura, data_encerramento,
               valor_estimado, uf, nicho, modalidade
        FROM editais
        WHERE uf = 'RJ'
          AND nicho = 'seguranca'
          AND status NOT IN ('arquivado', 'pregao_ext', 'encerrado', 'homologado', 'fracassado')
          AND (data_abertura IS NOT NULL OR data_encerramento IS NOT NULL)
    """).fetchall()
    conn.close()

    agora = datetime.now()
    for r in rows:
        # Confirma nicho em runtime
        if detectar_nicho(r["objeto"]) != "seguranca":
            continue
        stats["verificados"] += 1
        for campo in ("data_abertura", "data_encerramento"):
            dt = _parse_data(r[campo])
            if not dt or dt <= agora:
                continue
            horas = (dt - agora).total_seconds() / 3600

            for janela in JANELAS_HORAS:
                key = f"{r['pncp_id']}_{campo}_{janela}"
                if key in sent:
                    continue
                if abs(horas - janela) <= 0.5:
                    evento = "ABERTURA" if campo == "data_abertura" else "ENCERRAMENTO"
                    valor = r["valor_estimado"] or 0
                    objeto = (r["objeto"] or "")[:150]
                    msg = (
                        f"⏰ PRAZO {janela}h — {evento}\n"
                        f"📌 Modalidade: {r['modalidade'] or '-'}\n"
                        f"🏛 Órgão: {r['orgao_nome'][:60]}\n"
                        f"📍 UF: {r['uf']}\n"
                        f"🛠 Objeto: {objeto}\n"
                        f"📅 {dt.strftime('%d/%m/%Y %H:%M')}\n"
                        f"💰 Valor: R$ {_fmt_brl(valor)}\n"
                        f"🔗 https://pncp.gov.br/app/editais/{r['pncp_id'].replace('-', '/')}"
                    )
                    if _send_telegram(msg):
                        sent.add(key)
                        stats["alertas_enviados"] += 1
                        log.info(f"Alerta {janela}h enviado: {r['pncp_id']}")

    _save_sent(sent)
    return stats


def executar_loop(intervalo_min: int = 15):
    log.info(f"bot_prazos_seguranca iniciado. Intervalo: {intervalo_min}min")
    while True:
        try:
            log.info(f"Ciclo: {verificar_prazos()}")
        except Exception as e:
            log.error(f"Erro: {e}")
        time.sleep(intervalo_min * 60)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=int, default=15)
    args = ap.parse_args()
    if args.loop:
        executar_loop(args.intervalo)
    else:
        print(json.dumps(verificar_prazos(), indent=2, ensure_ascii=False))
