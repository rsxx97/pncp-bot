"""Bot Resultado — varre PNCP por homologações de editais que ENVIAMOS.

Diferente do absorvedor genérico (que varre nicho/UF):
1. Lê do DB editais com enviado_telegram=1 e data_encerramento já passada (3+ dias)
2. Pra cada item do edital, GET /itens/{num}/resultados
3. Atualiza editais.valor_homologado, valor_proposta, status='homologado'
4. Insere em participantes_licitacao (todos lances) e perfil_concorrente (vencedor)
5. Dispara aviso no canal Telegram do nicho com vencedor + valor + desconto

Sem LLM, sem custo — só HTTP + SQL.
"""
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent.parent
LICITACOES_AI = ROOT / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)
try:
    from config.settings import DB_PATH
except Exception:
    DB_PATH = LICITACOES_AI / "data" / "licitacoes.db"
from shared.nichos import rota_por_nicho

PNCP_V1 = "https://pncp.gov.br/api/pncp/v1"
HEADERS = {"User-Agent": "bot-resultado/1.0"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_resultado")


def _ensure_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS participantes_licitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pncp_id TEXT, cnpj TEXT, razao_social TEXT,
            posicao INTEGER, valor_proposta REAL, valor_referencia REAL,
            desconto_pct REAL,
            UNIQUE(pncp_id, cnpj, posicao)
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS perfil_concorrente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT UNIQUE, razao_social TEXT, uf TEXT, nichos TEXT,
            total_participacoes INTEGER DEFAULT 0,
            total_vitorias INTEGER DEFAULT 0,
            valor_total_ganho REAL DEFAULT 0,
            desconto_medio REAL DEFAULT 0,
            updated_at TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resultado_notificado (
            pncp_id TEXT PRIMARY KEY,
            notified_at TEXT
        )""")
    conn.commit()


def _get_resultados(cnpj: str, ano: str, seq: str) -> list[dict]:
    """Busca todos itens + resultados do edital."""
    try:
        r = httpx.get(f"{PNCP_V1}/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
                      headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return []
        itens = r.json() or []
    except Exception as e:
        log.warning(f"itens {cnpj}/{ano}/{seq}: {e}")
        return []

    out = []
    for item in itens:
        num = item.get("numeroItem")
        if not num:
            continue
        try:
            rr = httpx.get(
                f"{PNCP_V1}/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{num}/resultados",
                headers=HEADERS, timeout=15)
            if rr.status_code != 200:
                continue
            data = rr.json()
            resultados = data if isinstance(data, list) else data.get("data", [])
            for res in resultados:
                res["_item_num"] = num
                res["_valor_referencia"] = item.get("valorTotal") or item.get("valorUnitarioEstimado") or 0
                out.append(res)
        except Exception as e:
            log.warning(f"resultados it={num}: {e}")
    return out


def _formatar_aviso(ed: dict, vencedor: dict, total_part: int) -> str:
    valor_hom = vencedor.get("valor_homologado") or 0
    valor_ref = vencedor.get("valor_referencia") or ed.get("valor_estimado") or 0
    desconto = (1 - valor_hom / valor_ref) * 100 if valor_ref else 0
    nome_venc = vencedor.get("nome", "—")
    cnpj_venc = vencedor.get("cnpj", "—")
    msg = (
        f"🏁 RESULTADO HOMOLOGADO\n\n"
        f"📌 Edital: {ed['pncp_id']}\n"
        f"🏛 Órgão: {ed.get('orgao_nome') or '—'}\n"
        f"🛠 Objeto: {(ed.get('objeto') or '')[:200]}\n"
        f"💰 Estimado: R$ {valor_ref:,.2f}\n"
        f"🏆 Homologado: R$ {valor_hom:,.2f} ({desconto:+.2f}%)\n"
        f"🥇 Vencedor: {nome_venc} ({cnpj_venc})\n"
        f"👥 Participantes: {total_part}\n"
        f"🔗 {ed.get('link_edital') or '—'}"
    ).replace(",", "X").replace(".", ",").replace("X", ".")
    return msg


def _enviar_telegram(nicho: str, msg: str) -> bool:
    rota = rota_por_nicho(nicho)
    if not rota:
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{rota.token}/sendMessage",
            json={"chat_id": rota.chat_id, "text": msg, "disable_web_page_preview": True},
            timeout=15,
        )
        return r.status_code == 200
    except Exception:
        return False


def executar() -> dict:
    stats = {"editais_checados": 0, "fechados": 0, "novos_vencedores": 0,
             "notificados": 0, "sem_resultado": 0}
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)

    # Busca editais que enviamos cuja data_encerramento foi entre 3 e 90 dias atrás
    inicio = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    fim = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT * FROM editais
         WHERE enviado_telegram = 1
           AND date(data_encerramento) BETWEEN date(?) AND date(?)
           AND (status IS NULL OR status NOT IN ('homologado', 'fracassado'))
         ORDER BY data_encerramento DESC
         LIMIT 100
    """, (inicio, fim)).fetchall()
    log.info(f"{len(rows)} editais enviados aguardando resultado (encerrou entre {inicio} e {fim})")

    for r in rows:
        pid = r["pncp_id"]
        try:
            cnpj_org, ano, seq = pid.split("-")
        except ValueError:
            continue
        stats["editais_checados"] += 1

        resultados = _get_resultados(cnpj_org, ano, seq)
        if not resultados:
            stats["sem_resultado"] += 1
            continue

        # Agrupa por item -> classificação 1 = vencedor
        vencedor_total_valor = 0
        vencedor_obj = None
        cnpjs_part = set()

        for res in resultados:
            nome_venc = res.get("nomeRazaoSocialFornecedor", "")
            cnpj_venc = (res.get("niFornecedor", "") or "").replace(".", "").replace("/", "").replace("-", "")
            valor_hom = res.get("valorTotalHomologado") or 0
            posicao = res.get("ordenClassificacao", 0)
            valor_ref = res.get("_valor_referencia", 0)
            if not nome_venc:
                continue
            cnpjs_part.add(cnpj_venc)
            desconto = round((1 - valor_hom / valor_ref) * 100, 2) if valor_ref and valor_hom else 0
            conn.execute("""
                INSERT OR IGNORE INTO participantes_licitacao
                (pncp_id, cnpj, razao_social, posicao, valor_proposta, valor_referencia, desconto_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pid, cnpj_venc, nome_venc, posicao, valor_hom, valor_ref, desconto))

            if posicao == 1:
                vencedor_total_valor += valor_hom or 0
                vencedor_obj = {
                    "nome": nome_venc, "cnpj": cnpj_venc,
                    "valor_homologado": valor_hom,
                    "valor_referencia": valor_ref,
                }
                # perfil concorrente
                row_p = conn.execute(
                    "SELECT id, nichos, total_vitorias, valor_total_ganho FROM perfil_concorrente WHERE cnpj=?",
                    (cnpj_venc,)).fetchone()
                nicho_ed = (r["nicho"] or "outros")
                if row_p:
                    nichos_atuais = row_p[1] or ""
                    nichos_novo = nichos_atuais if nicho_ed in nichos_atuais else (
                        f"{nichos_atuais},{nicho_ed}" if nichos_atuais else nicho_ed)
                    conn.execute("""
                        UPDATE perfil_concorrente
                           SET total_vitorias = total_vitorias + 1,
                               valor_total_ganho = COALESCE(valor_total_ganho,0) + ?,
                               nichos = ?,
                               updated_at = datetime('now')
                         WHERE cnpj=?
                    """, (valor_hom or 0, nichos_novo, cnpj_venc))
                else:
                    stats["novos_vencedores"] += 1
                    conn.execute("""
                        INSERT INTO perfil_concorrente
                        (cnpj, razao_social, uf, nichos,
                         total_participacoes, total_vitorias, valor_total_ganho, desconto_medio, updated_at)
                        VALUES (?, ?, ?, ?, 1, 1, ?, ?, datetime('now'))
                    """, (cnpj_venc, nome_venc, r["uf"] or "", nicho_ed, valor_hom or 0, desconto))

        if vencedor_obj:
            stats["fechados"] += 1
            conn.execute("""
                UPDATE editais SET valor_proposta = ?, status = 'homologado', updated_at = datetime('now')
                 WHERE pncp_id = ?
            """, (vencedor_total_valor, pid))

            # Notifica 1x
            ja_notif = conn.execute(
                "SELECT 1 FROM resultado_notificado WHERE pncp_id=?", (pid,)).fetchone()
            if not ja_notif:
                msg = _formatar_aviso(dict(r), vencedor_obj, len(cnpjs_part))
                nicho_ed = r["nicho"] or "outros"
                if _enviar_telegram(nicho_ed, msg):
                    conn.execute("INSERT OR REPLACE INTO resultado_notificado (pncp_id, notified_at) VALUES (?, datetime('now'))",
                                 (pid,))
                    stats["notificados"] += 1
                    log.info(f"✓ {pid}: {vencedor_obj['nome']} R$ {vencedor_total_valor:,.2f}")
                    time.sleep(2)

        conn.commit()
        time.sleep(0.5)

    conn.close()
    log.info(f"Bot Resultado: {json.dumps(stats, ensure_ascii=False)}")
    return stats


if __name__ == "__main__":
    executar()
