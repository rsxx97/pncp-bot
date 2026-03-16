import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "licitacoes.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS oportunidades (
            id TEXT PRIMARY KEY,
            portal TEXT NOT NULL DEFAULT 'PNCP',
            modalidade_cod INTEGER,
            modalidade_nome TEXT,
            orgao TEXT,
            unidade TEXT,
            uf TEXT,
            objeto TEXT,
            valor_estimado REAL,
            data_publicacao TEXT,
            data_abertura TEXT,
            data_encerramento TEXT,
            link TEXT,
            cnpj TEXT,
            ano_compra TEXT,
            seq_compra TEXT,
            enviado_telegram INTEGER DEFAULT 0,
            favorito INTEGER DEFAULT 0,
            status TEXT DEFAULT 'nova',
            notas TEXT DEFAULT '',
            criado_em TEXT DEFAULT (datetime('now','localtime')),
            atualizado_em TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_uf ON oportunidades(uf);
        CREATE INDEX IF NOT EXISTS idx_modalidade ON oportunidades(modalidade_cod);
        CREATE INDEX IF NOT EXISTS idx_status ON oportunidades(status);
        CREATE INDEX IF NOT EXISTS idx_valor ON oportunidades(valor_estimado);
        CREATE INDEX IF NOT EXISTS idx_data_pub ON oportunidades(data_publicacao);
        CREATE INDEX IF NOT EXISTS idx_portal ON oportunidades(portal);
    """)
    conn.commit()
    conn.close()


def inserir_oportunidade(op):
    conn = get_db()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO oportunidades
            (id, portal, modalidade_cod, modalidade_nome, orgao, unidade, uf,
             objeto, valor_estimado, data_publicacao, data_abertura,
             data_encerramento, link, cnpj, ano_compra, seq_compra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            op["id"], op.get("portal", "PNCP"),
            op.get("modalidade_cod"), op.get("modalidade_nome"),
            op.get("orgao"), op.get("unidade"), op.get("uf"),
            op.get("objeto"), op.get("valor_estimado"),
            op.get("data_publicacao"), op.get("data_abertura"),
            op.get("data_encerramento"), op.get("link"),
            op.get("cnpj"), op.get("ano_compra"), op.get("seq_compra"),
        ))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def marcar_enviado(id_op):
    conn = get_db()
    conn.execute("UPDATE oportunidades SET enviado_telegram=1 WHERE id=?", (id_op,))
    conn.commit()
    conn.close()


def listar_oportunidades(filtros=None):
    conn = get_db()
    query = "SELECT * FROM oportunidades WHERE 1=1"
    params = []

    if filtros:
        if filtros.get("uf"):
            query += " AND uf = ?"
            params.append(filtros["uf"])
        if filtros.get("modalidade"):
            query += " AND modalidade_cod = ?"
            params.append(filtros["modalidade"])
        if filtros.get("status"):
            query += " AND status = ?"
            params.append(filtros["status"])
        if filtros.get("favorito"):
            query += " AND favorito = 1"
        if filtros.get("portal"):
            query += " AND portal = ?"
            params.append(filtros["portal"])
        if filtros.get("valor_min"):
            query += " AND valor_estimado >= ?"
            params.append(filtros["valor_min"])
        if filtros.get("valor_max"):
            query += " AND valor_estimado <= ?"
            params.append(filtros["valor_max"])
        if filtros.get("busca"):
            query += " AND objeto LIKE ?"
            params.append(f"%{filtros['busca']}%")
        if filtros.get("data_de"):
            query += " AND data_publicacao >= ?"
            params.append(filtros["data_de"])
        if filtros.get("data_ate"):
            query += " AND data_publicacao <= ?"
            params.append(filtros["data_ate"])

    query += " ORDER BY data_publicacao DESC, valor_estimado DESC"

    if filtros and filtros.get("limite"):
        query += " LIMIT ?"
        params.append(filtros["limite"])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def atualizar_status(id_op, status):
    conn = get_db()
    conn.execute("UPDATE oportunidades SET status=?, atualizado_em=datetime('now','localtime') WHERE id=?",
                 (status, id_op))
    conn.commit()
    conn.close()


def toggle_favorito(id_op):
    conn = get_db()
    conn.execute("UPDATE oportunidades SET favorito = CASE WHEN favorito=1 THEN 0 ELSE 1 END, atualizado_em=datetime('now','localtime') WHERE id=?",
                 (id_op,))
    conn.commit()
    row = conn.execute("SELECT favorito FROM oportunidades WHERE id=?", (id_op,)).fetchone()
    conn.close()
    return dict(row)["favorito"] if row else 0


def salvar_notas(id_op, notas):
    conn = get_db()
    conn.execute("UPDATE oportunidades SET notas=?, atualizado_em=datetime('now','localtime') WHERE id=?",
                 (notas, id_op))
    conn.commit()
    conn.close()


def estatisticas():
    conn = get_db()
    stats = {}
    stats["total"] = conn.execute("SELECT COUNT(*) FROM oportunidades").fetchone()[0]
    stats["novas"] = conn.execute("SELECT COUNT(*) FROM oportunidades WHERE status='nova'").fetchone()[0]
    stats["em_analise"] = conn.execute("SELECT COUNT(*) FROM oportunidades WHERE status='em_analise'").fetchone()[0]
    stats["favoritas"] = conn.execute("SELECT COUNT(*) FROM oportunidades WHERE favorito=1").fetchone()[0]
    stats["valor_total"] = conn.execute("SELECT COALESCE(SUM(valor_estimado),0) FROM oportunidades").fetchone()[0]
    stats["por_uf"] = [dict(r) for r in conn.execute(
        "SELECT uf, COUNT(*) as qtd FROM oportunidades GROUP BY uf ORDER BY qtd DESC"
    ).fetchall()]
    stats["por_modalidade"] = [dict(r) for r in conn.execute(
        "SELECT modalidade_nome, COUNT(*) as qtd FROM oportunidades GROUP BY modalidade_nome ORDER BY qtd DESC"
    ).fetchall()]
    stats["por_portal"] = [dict(r) for r in conn.execute(
        "SELECT portal, COUNT(*) as qtd FROM oportunidades GROUP BY portal ORDER BY qtd DESC"
    ).fetchall()]
    conn.close()
    return stats


if __name__ == "__main__":
    init_db()
    print(f"Banco de dados criado em: {DB_PATH}")
