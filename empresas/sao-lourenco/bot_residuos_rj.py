"""Bot dedicado — dispara editais de RESIDUOS RJ no canal Telegram SL-RESIDUOS.

Escopo fixo:
  - UF = RJ
  - nicho = residuos
  - modalidades = concorrencia + pregao + dispensa + inexigibilidade
  - status aberto (data_encerramento > agora, nao homologado/fracassado/arquivado)

Dedup: grava IDs enviados em data/skills/residuos_rj_sent.json. Zero API.
"""
import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "licitacoes-ai"))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / "licitacoes-ai" / ".env", override=True)

from config.settings import DB_PATH
from shared.nichos import detectar_nicho, formatar_edital, enviar_para_nicho

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_residuos_rj")

SENT_FILE = Path(__file__).parent.parent / "data" / "skills" / "residuos_rj_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

MODALIDADES_ACEITAS = (
    # Modalidades com disputa real
    "Pregão Eletrônico", "Pregão Presencial",
    "Concorrência", "Concorrência - Loss",
    "Tomada de Preços", "Convite",
    # Dispensa tambem — pode ser cotação aberta
    "Dispensa", "Dispensa de Licitação",
)
# Contratação direta (prefixa aviso no Telegram pro usuário decidir)
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


def executar() -> dict:
    """Dispara editais abertos — resíduos + transporte + carga perigosa + variados + Petrobras.

    Cobertura: BRASIL (não só RJ) para Petrobras + carga perigosa.
    Cobertura RJ específica: resíduos + transporte local.
    """
    stats = {"encontrados": 0, "enviados": 0, "ja_enviados": 0, "falhas": 0,
             "por_categoria": {}}
    sent = _load_sent()
    agora = datetime.now().isoformat()

    # Importa keywords do bot_sistema_s (fonte única)
    sys.path.insert(0, str(Path(__file__).parent))
    from bot_sistema_s import (
        KEYWORDS_RESIDUOS, KEYWORDS_TRANSPORTE,
        KEYWORDS_CARGA_PERIGOSA, KEYWORDS_VARIADOS,
        _classificar_nicho,
    )

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row

    # 1. RJ (residuos + transporte local) + 2. BR (Petrobras + carga perigosa)
    rows = conn.execute("""
        SELECT * FROM editais
        WHERE (data_encerramento IS NULL OR data_encerramento > ?)
          AND objeto IS NOT NULL
        ORDER BY data_publicacao DESC
        LIMIT 2000
    """, (agora,)).fetchall()

    stats["encontrados"] = len(rows)

    for r in rows:
        pid = r["pncp_id"]
        obj = r["objeto"] or ""
        uf = r["uf"] or ""
        orgao = (r["orgao_nome"] or "").lower()

        # Classifica nicho pelo objeto
        nicho_cat = _classificar_nicho(obj)

        # Detecta Petrobras
        eh_petrobras = (
            "petrobras" in orgao or "petróleo brasileiro" in orgao or
            "transpetro" in orgao or
            (r["orgao_cnpj"] or "").startswith("33000167")
        )

        # Filtro ESTRITO (canal resíduos):
        # 1. Resíduos RJ (nicho puro)
        # 2. Petrobras (qualquer UF) — é especializada em carga perigosa/offshore
        # Transporte genérico (alunos/passageiros) NÃO entra
        if eh_petrobras:
            pass  # aceita Petrobras em qualquer UF
        elif uf == "RJ" and nicho_cat == "residuos":
            pass  # RJ resíduos
        else:
            continue  # nada mais

        if pid in sent:
            stats["ja_enviados"] += 1
            continue

        # Prefixo por categoria
        prefix_map = {
            "residuos": "♻️ RESÍDUOS",
            "transporte": "🚛 TRANSPORTE",
            "carga_perigosa": "⚠️ CARGA PERIGOSA",
            "variados": "🛠 VARIADOS",
            "obra": "🏗 OBRA",
            "servico": "🔧 SERVIÇO",
        }
        prefix = "🛢 PETROBRAS" if eh_petrobras else prefix_map.get(nicho_cat, "📌 GERAL")

        msg = formatar_edital(dict(r))
        # Avisos
        modal = (r["modalidade"] or "").strip()
        if any(m in modal for m in MODALIDADES_CONTRATACAO_DIRETA):
            msg = "⚠️ CONTRATAÇÃO DIRETA — verifique se é cotação aberta\n\n" + msg
        msg = f"{prefix}\n\n" + msg

        if enviar_para_nicho(msg, "residuos", parse_mode=None):
            sent.add(pid)
            stats["enviados"] += 1
            stats["por_categoria"][prefix] = stats["por_categoria"].get(prefix, 0) + 1
            log.info(f"Enviado [{prefix}]: {pid}")
            _save_sent(sent)  # salva incremental
            import time
            time.sleep(2.5)  # respeita rate limit Telegram (~20 msg/min)
        else:
            stats["falhas"] += 1
            import time
            time.sleep(5)  # em caso de erro/429, espera mais

    _save_sent(sent)
    conn.close()
    conn.close()
    return stats


def executar_loop(intervalo_min: int = 30):
    log.info(f"bot_residuos_rj iniciado. Intervalo: {intervalo_min}min")
    while True:
        try:
            log.info(f"Ciclo: {executar()}")
        except Exception as e:
            log.error(f"Erro: {e}")
        time.sleep(intervalo_min * 60)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=int, default=30, help="Minutos entre ciclos")
    ap.add_argument("--reset", action="store_true", help="Limpa historico de enviados")
    args = ap.parse_args()
    if args.reset:
        SENT_FILE.unlink(missing_ok=True)
        print("Historico reset.")
    if args.loop:
        executar_loop(args.intervalo)
    else:
        print(json.dumps(executar(), indent=2, ensure_ascii=False))
