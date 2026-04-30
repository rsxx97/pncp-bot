"""Bot dedicado — dispara editais de SEGURANCA/VIGILANCIA RJ no canal Telegram MIAMI-VIGILANCIA.

Cliente: Miami Vigilancia e Seguranca LTDA — CNPJ 01.891.421/0001-12
CNAE: 80.11-1-01 (Vigilancia e seguranca privada)
Canal Telegram: MIAMI VIGILANCIA E SEGURANCA (@Miami_SV_Bot)

Escopo fixo:
  - UF = RJ
  - nicho = seguranca
  - modalidades = concorrencia + pregao + dispensa + inexigibilidade
  - status aberto (data_encerramento > agora, nao homologado/fracassado/arquivado)

Dedup: grava IDs enviados em data/vigilancia_rj_sent.json. Zero API.
"""
import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# Importa modulos do licitacoes-ai
LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)

from config.settings import DB_PATH
from shared.nichos import detectar_nicho, formatar_edital, enviar_para_nicho
from agente1_monitor.pncp_client import buscar_editais_por_texto

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_vigilancia_rj")

SENT_FILE = Path(__file__).parent / "data" / "miami_seguranca_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Migra arquivo antigo para o novo (unificado)
_OLD_SENT = Path(__file__).parent / "data" / "vigilancia_rj_sent.json"
if _OLD_SENT.exists() and not SENT_FILE.exists():
    _OLD_SENT.rename(SENT_FILE)
elif _OLD_SENT.exists():
    # Merge antigo no novo
    _old = set(json.loads(_OLD_SENT.read_text(encoding="utf-8")))
    _new = set(json.loads(SENT_FILE.read_text(encoding="utf-8"))) if SENT_FILE.exists() else set()
    SENT_FILE.write_text(json.dumps(sorted(_old | _new)), encoding="utf-8")
    _OLD_SENT.unlink()

MODALIDADES_ACEITAS = (
    "Pregão Eletrônico", "Pregão Presencial",
    "Concorrência", "Concorrência - Loss",
    "Tomada de Preços", "Convite",
    "Dispensa", "Dispensa de Licitação",  # com aviso no Telegram
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


def executar() -> dict:
    """Dispara editais novos seguranca/vigilancia RJ abertos."""
    stats = {"encontrados": 0, "enviados": 0, "ja_enviados": 0, "falhas": 0}
    sent = _load_sent()
    agora = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM editais
        WHERE uf = 'RJ'
          AND nicho = 'seguranca'
          AND status NOT IN ('arquivado', 'pregao_ext', 'homologado', 'fracassado', 'encerrado')
          AND (data_encerramento IS NULL OR data_encerramento > ?)
        ORDER BY data_encerramento ASC
    """, (agora,)).fetchall()

    stats["encontrados"] = len(rows)
    log.info(f"Seguranca RJ abertos: {len(rows)}")

    for r in rows:
        pid = r["pncp_id"]
        # Confirma nicho em runtime
        if detectar_nicho(r["objeto"]) != "seguranca":
            continue
        if pid in sent:
            stats["ja_enviados"] += 1
            continue
        msg = formatar_edital(dict(r))
        modal = (r["modalidade"] or "").strip()
        if any(m in modal for m in MODALIDADES_CONTRATACAO_DIRETA):
            msg = "⚠️ CONTRATAÇÃO DIRETA — verifique se é cotação aberta\n\n" + msg
        if enviar_para_nicho(msg, "seguranca", parse_mode=None):
            sent.add(pid)
            stats["enviados"] += 1
            log.info(f"Enviado: {pid} | {r['orgao_nome'][:40]}")
        else:
            stats["falhas"] += 1
            log.warning(f"Falha: {pid}")

    _save_sent(sent)
    conn.close()
    return stats


def recuperar_editais_abertos() -> dict:
    """Busca editais abertos no PNCP por texto — recupera publicados ha meses.

    Complementa o monitor padrao que so busca publicacoes recentes (3 dias).
    Roda 1x por dia para nao sobrecarregar a API.
    """
    stats = {"buscados": 0, "novos": 0, "ja_existem": 0}
    conn = sqlite3.connect(DB_PATH)

    TERMOS_BUSCA = [
        "vigilancia armada",
        "vigilancia patrimonial",
        "seguranca armada",
        "seguranca patrimonial",
    ]

    pncp_ids_existentes = set(
        r[0] for r in conn.execute("SELECT pncp_id FROM editais").fetchall()
    )

    for termo in TERMOS_BUSCA:
        try:
            items = buscar_editais_por_texto(
                query=termo,
                tam_pagina=50,
                paginas=3,
                status="recebendo_proposta",
                uf="RJ",
            )
            stats["buscados"] += len(items)
            for it in items:
                pid = it.get("pncp_id", "")
                if not pid or pid in pncp_ids_existentes:
                    stats["ja_existem"] += 1
                    continue
                # Verifica se e realmente seguranca
                objeto = it.get("title", it.get("objeto", ""))
                if detectar_nicho(objeto) != "seguranca":
                    continue
                # Insere no banco
                conn.execute(
                    """INSERT OR IGNORE INTO editais
                    (pncp_id, orgao_nome, objeto, modalidade, valor_estimado,
                     data_encerramento, uf, municipio, link_edital, status, nicho,
                     score_relevancia, fonte)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid,
                     it.get("orgao", it.get("orgao_nome", "")),
                     objeto,
                     it.get("modalidade", "Pregao Eletronico"),
                     it.get("valor_estimado", 0),
                     it.get("data_encerramento", ""),
                     "RJ", it.get("municipio", ""),
                     f"https://pncp.gov.br/app/editais/{pid.replace('-', '/', 2)}",
                     "novo", "seguranca", 80, "PNCP"),
                )
                pncp_ids_existentes.add(pid)
                stats["novos"] += 1
                log.info(f"Recuperado: {pid} | {objeto[:60]}")
        except Exception as e:
            log.warning(f"Busca '{termo}': {e}")

    conn.commit()
    conn.close()
    log.info(f"Recuperacao: {stats}")
    return stats


def executar_completo() -> dict:
    """Executa busca normal + recuperacao de editais antigos."""
    stats_recuperacao = recuperar_editais_abertos()
    stats_envio = executar()
    return {"recuperacao": stats_recuperacao, "envio": stats_envio}


def executar_loop(intervalo_min: int = 30):
    log.info(f"bot_vigilancia_rj iniciado. Intervalo: {intervalo_min}min")
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
