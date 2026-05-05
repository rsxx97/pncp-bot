"""Helper compartilhado: grava editais dos bots de nicho no DB AI unificado.

Uso nos bots Obra/MDO/Aquisição TI/etc:
    from core.skills._db_helper import gravar_edital
    gravar_edital(ed, nicho="obra", enviado=True)

Idempotente (UPSERT por pncp_id).
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
LICITACOES_AI = ROOT / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
try:
    from config.settings import DB_PATH
except Exception:
    DB_PATH = LICITACOES_AI / "data" / "licitacoes.db"


def gravar_edital(ed: dict, nicho: str, enviado: bool = False) -> bool:
    """UPSERT no DB AI unificado. ed deve ter pelo menos pncp_id e objeto.

    Não falha o envio se DB indisponível — só loga e retorna False.
    """
    pid = ed.get("pncp_id")
    objeto = ed.get("objeto") or ""
    if not pid or not objeto:
        return False

    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()
        cnpj, ano, seq = pid.split("-") if pid.count("-") == 2 else (None, None, None)
        c.execute("""
            INSERT INTO editais (
                pncp_id, orgao_cnpj, orgao_nome, objeto, valor_estimado,
                data_publicacao, data_abertura, data_encerramento,
                modalidade, link_edital, uf, fonte, nicho,
                enviado_telegram, notificado_telegram
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pncp_id) DO UPDATE SET
                orgao_nome = COALESCE(excluded.orgao_nome, orgao_nome),
                objeto = COALESCE(excluded.objeto, objeto),
                valor_estimado = COALESCE(excluded.valor_estimado, valor_estimado),
                data_abertura = COALESCE(excluded.data_abertura, data_abertura),
                data_encerramento = COALESCE(excluded.data_encerramento, data_encerramento),
                modalidade = COALESCE(excluded.modalidade, modalidade),
                nicho = COALESCE(excluded.nicho, nicho),
                enviado_telegram = MAX(excluded.enviado_telegram, enviado_telegram),
                notificado_telegram = MAX(excluded.notificado_telegram, notificado_telegram),
                updated_at = datetime('now')
        """, (
            pid, cnpj, ed.get("orgao_nome") or "", objeto,
            ed.get("valor_estimado"),
            ed.get("data_publicacao") or "",
            ed.get("data_abertura") or "",
            ed.get("data_encerramento") or "",
            ed.get("modalidade") or "",
            ed.get("link_edital") or "",
            ed.get("uf") or "",
            ed.get("fonte") or "pncp",
            nicho,
            1 if enviado else 0,
            1 if enviado else 0,
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        # Não derruba o bot se o DB estiver indisponível
        import logging
        logging.getLogger(__name__).warning(f"DB gravar_edital falhou {pid}: {e}")
        return False
