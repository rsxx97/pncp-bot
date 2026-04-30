"""Sao Lourenco Ambiental — Radar de Licitacoes de Residuos RJ.

Roda PNCP + portais externos, dedup, envia pro Telegram.
Uso:
    python run.py              # One-shot (PNCP + portais)
    python run.py --pncp       # Somente PNCP
    python run.py --portais    # Somente portais externos
    python run.py --loop       # Loop a cada 2h (PNCP + portais)
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("sao_lourenco_radar")

LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)


def rodar_pncp():
    from bot_residuos_rj import executar
    return executar()


def rodar_portais():
    from bot_sistema_s import executar
    return executar()


def rodar_tudo():
    log.info("=== SAO LOURENCO RADAR — INICIO ===")
    stats = {}
    log.info("[1/2] PNCP...")
    try:
        stats["pncp"] = rodar_pncp()
    except Exception as e:
        log.error(f"PNCP erro: {e}")
        stats["pncp"] = {"erro": str(e)}
    log.info("[2/2] Portais...")
    try:
        stats["portais"] = rodar_portais()
    except Exception as e:
        log.error(f"Portais erro: {e}")
        stats["portais"] = {"erro": str(e)}
    log.info(f"=== SAO LOURENCO RADAR — FIM === {json.dumps(stats, ensure_ascii=False)}")
    return stats


def rodar_loop(intervalo_min: int = 120):
    log.info(f"Sao Lourenco Radar em loop. Intervalo: {intervalo_min}min")
    while True:
        try:
            rodar_tudo()
        except Exception as e:
            log.error(f"Erro ciclo: {e}")
        time.sleep(intervalo_min * 60)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sao Lourenco — Radar de Residuos RJ")
    ap.add_argument("--pncp", action="store_true")
    ap.add_argument("--portais", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=int, default=120)
    args = ap.parse_args()
    if args.loop:
        rodar_loop(args.intervalo)
    elif args.pncp:
        print(json.dumps(rodar_pncp(), indent=2, ensure_ascii=False))
    elif args.portais:
        print(json.dumps(rodar_portais(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(rodar_tudo(), indent=2, ensure_ascii=False))
