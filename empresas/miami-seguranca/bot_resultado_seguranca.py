"""Bot de resultados — polla PNCP procurando homologacao dos editais de SEGURANCA.

Marca status='homologado', salva vencedor/valor, notifica canal MIAMI VIGILANCIA.
Zero API — usa endpoint publico PNCP.
"""
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)

from config.settings import DB_PATH, PNCP_BASE_URL
from shared.nichos import detectar_nicho

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_resultado_seguranca")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_SEGURANCA")
CHAT_ID = os.getenv("TELEGRAM_CHAT_SEGURANCA")


def _fmt_brl(v):
    try:
        v = float(v)
        inteiro = int(v)
        centavos = round((v - inteiro) * 100)
        s = f"{inteiro:,}".replace(",", ".")
        return f"{s},{centavos:02d}"
    except Exception:
        return f"{v}"


def _send_telegram(msg: str):
    if not (BOT_TOKEN and CHAT_ID):
        log.warning(f"SEM TELEGRAM: {msg}")
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=15,
        )
    except Exception as e:
        log.error(f"telegram: {e}")


def _buscar_resultados_pncp(cnpj: str, ano: str, seq: str) -> list[dict]:
    url = f"{PNCP_BASE_URL}/orgaos/{cnpj}/compras/{ano}/{seq}/resultados"
    try:
        r = httpx.get(url, timeout=30)
        if r.status_code == 200:
            return r.json() or []
    except Exception as e:
        log.debug(f"resultado {cnpj}/{ano}/{seq}: {e}")
    return []


# CNPJ Miami para comparacao de resultado
MIAMI_CNPJ = "01891421000112"


def verificar_resultados(limit: int = 50) -> dict:
    stats = {"verificados": 0, "com_resultado": 0, "ganhos": 0, "perdidos": 0}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    agora = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    rows = conn.execute("""
        SELECT pncp_id, orgao_nome, objeto, data_abertura, valor_estimado,
               valor_proposta, empresa_sugerida, modalidade
        FROM editais
        WHERE uf = 'RJ'
          AND nicho = 'seguranca'
          AND status NOT IN ('arquivado', 'pregao_ext', 'homologado', 'fracassado')
          AND data_abertura IS NOT NULL AND data_abertura <= ?
        ORDER BY data_abertura DESC
        LIMIT ?
    """, (agora, limit)).fetchall()

    for r in rows:
        # Confirma nicho
        if detectar_nicho(r["objeto"]) != "seguranca":
            continue
        stats["verificados"] += 1
        parts = r["pncp_id"].split("-")
        if len(parts) < 3:
            continue
        cnpj, ano, seq = parts[0], parts[1], parts[2]
        resultados = _buscar_resultados_pncp(cnpj, ano, seq)
        if not resultados:
            continue

        stats["com_resultado"] += 1
        vencedor = resultados[0] if isinstance(resultados, list) else resultados
        cnpj_vencedor = (vencedor.get("niFornecedor") or "").replace(".", "").replace("/", "").replace("-", "")
        valor_vencedor = vencedor.get("valorHomologado") or vencedor.get("valorAdjudicado") or 0
        nome_vencedor = vencedor.get("nomeRazaoSocialFornecedor", "?")

        ganhamos = MIAMI_CNPJ == cnpj_vencedor

        if ganhamos:
            stats["ganhos"] += 1
            emoji = "🏆"
            titulo = "GANHAMOS!"
        else:
            stats["perdidos"] += 1
            emoji = "❌"
            titulo = "PERDEMOS"

        objeto = (r["objeto"] or "")[:120]
        msg = (
            f"{emoji} {titulo}\n"
            f"📌 Modalidade: {r['modalidade'] or '-'}\n"
            f"🏛 Órgão: {r['orgao_nome'][:60]}\n"
            f"🛠 Objeto: {objeto}\n"
            f"🥇 Vencedor: {nome_vencedor[:50]}\n"
            f"💰 Valor homologado: R$ {_fmt_brl(valor_vencedor)}\n"
            f"📊 Nossa proposta: R$ {_fmt_brl(r['valor_proposta'] or 0)}\n"
            f"🔗 https://pncp.gov.br/app/editais/{r['pncp_id'].replace('-', '/')}"
        )
        _send_telegram(msg)

        conn.execute(
            "UPDATE editais SET status=?, updated_at=datetime('now') WHERE pncp_id=?",
            ("homologado", r["pncp_id"]),
        )
        conn.commit()
        log.info(f"Resultado: {r['pncp_id']} -> {'GANHOU' if ganhamos else 'PERDEU'} R$ {valor_vencedor}")

    conn.close()
    return stats


def executar_loop(intervalo_min: int = 60):
    log.info(f"bot_resultado_seguranca iniciado. Intervalo: {intervalo_min}min")
    while True:
        try:
            log.info(f"Ciclo: {verificar_resultados()}")
        except Exception as e:
            log.error(f"Erro: {e}")
        time.sleep(intervalo_min * 60)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=int, default=60)
    args = ap.parse_args()
    if args.loop:
        executar_loop(args.intervalo)
    else:
        print(json.dumps(verificar_resultados(), indent=2, ensure_ascii=False))
