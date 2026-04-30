"""Bot de habilitacao — valida certidoes (CND, FGTS, CNDT) da Miami Vigilancia.

Le config/miami_habilitacao.json, checa validades, notifica canal MIAMI VIGILANCIA
quando certidao expira em <=10 dias ou ja esta vencida. Zero API.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, date
from pathlib import Path

import httpx

LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_habilitacao_seguranca")

CONFIG_PATH = Path(__file__).parent / "config" / "miami_habilitacao.json"
OUT_DIR = Path(__file__).parent / "data" / "habilitacao"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SENT_FILE = Path(__file__).parent / "data" / "habilitacao_sent.json"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_SEGURANCA")
CHAT_ID = os.getenv("TELEGRAM_CHAT_SEGURANCA")

CERTIDOES = [
    ("cnd_federal", "Certidão Negativa Federal (Receita + PGFN)"),
    ("cnd_fgts", "CND FGTS (Caixa)"),
    ("cnd_trabalhista", "CNDT (TST)"),
    ("cnd_estadual", "CND Estadual"),
    ("cnd_municipal", "CND Municipal"),
    ("cnd_falencia", "Certidão de Falência/Concordata"),
    ("alvara_pf", "Alvará de Funcionamento PF"),
    ("csv_vigilancia", "CSV - Certificado de Segurança de Vigilância"),
    ("registro_cra", "Registro CRA (Conselho Regional de Administração)"),
]


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


def _parse_validade(s: str) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def _load_sent() -> set:
    if SENT_FILE.exists():
        return set(json.loads(SENT_FILE.read_text(encoding="utf-8")))
    return set()


def _save_sent(s: set):
    SENT_FILE.write_text(json.dumps(sorted(s)), encoding="utf-8")


def checar_empresa(empresa: dict) -> dict:
    nome = empresa.get("nome_fantasia") or empresa.get("razao_social", "?")
    cnpj = empresa.get("cnpj", "")
    certs = empresa.get("certidoes", {})

    hoje = date.today()
    resultados = {}
    for chave, label in CERTIDOES:
        c = certs.get(chave, {})
        val_str = c.get("validade")
        val = _parse_validade(val_str)
        if not val:
            resultados[chave] = {"label": label, "status": "SEM_DATA", "dias": None}
            continue
        dias = (val - hoje).days
        if dias < 0:
            status = "VENCIDA"
        elif dias <= 10:
            status = "URGENTE"
        elif dias <= 30:
            status = "ATENCAO"
        else:
            status = "OK"
        resultados[chave] = {"label": label, "status": status, "dias": dias, "validade": val_str}

    return {
        "empresa": nome,
        "cnpj": cnpj,
        "checado_em": datetime.now().isoformat(),
        "certidoes": resultados,
    }


def executar(notificar: bool = True) -> dict:
    stats = {"empresas": 0, "vencidas": 0, "urgentes": 0, "ok": 0}
    if not CONFIG_PATH.exists():
        log.error(f"Config nao encontrada: {CONFIG_PATH}")
        return stats

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    sent = _load_sent() if notificar else set()

    for emp in cfg.get("empresas", []):
        stats["empresas"] += 1
        r = checar_empresa(emp)
        out_path = OUT_DIR / f"status_miami.json"
        out_path.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

        problemas = []
        for chave, info in r["certidoes"].items():
            if info["status"] == "VENCIDA":
                stats["vencidas"] += 1
                problemas.append(f"❌ {info['label']}: VENCIDA há {-info['dias']}d")
            elif info["status"] == "URGENTE":
                stats["urgentes"] += 1
                problemas.append(f"🔴 {info['label']}: vence em {info['dias']}d")
            elif info["status"] == "ATENCAO":
                problemas.append(f"🟡 {info['label']}: vence em {info['dias']}d")
            elif info["status"] == "OK":
                stats["ok"] += 1
            else:
                problemas.append(f"⚠ {info['label']}: sem validade cadastrada")

        if notificar and problemas:
            chave_dia = f"miami_{date.today().isoformat()}"
            if chave_dia not in sent:
                msg = f"🛡 HABILITAÇÃO — {r['empresa']}\n\n" + "\n".join(problemas[:10])
                _send_telegram(msg)
                sent.add(chave_dia)
                log.info(f"Notificado: {r['empresa']} ({len(problemas)} pendencias)")

    if notificar:
        _save_sent(sent)

    return stats


def executar_loop(intervalo_horas: int = 12):
    log.info(f"bot_habilitacao_seguranca iniciado. Intervalo: {intervalo_horas}h")
    while True:
        try:
            log.info(f"Ciclo: {executar()}")
        except Exception as e:
            log.error(f"Erro: {e}")
        time.sleep(intervalo_horas * 3600)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=int, default=12)
    ap.add_argument("--silencioso", action="store_true")
    args = ap.parse_args()
    if args.loop:
        executar_loop(args.intervalo)
    else:
        print(json.dumps(executar(notificar=not args.silencioso), indent=2, ensure_ascii=False))
