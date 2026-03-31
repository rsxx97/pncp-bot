"""SQLite database manager — schema, init, CRUD."""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import DB_PATH, DATA_DIR

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """Retorna conexão SQLite com row_factory = sqlite3.Row."""
    if not hasattr(_local, "conn") or _local.conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(DB_PATH), timeout=10)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def close_db():
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        _local.conn = None


# ── Schema ────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Editais monitorados
CREATE TABLE IF NOT EXISTS editais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pncp_id TEXT UNIQUE NOT NULL,
    orgao_cnpj TEXT,
    orgao_nome TEXT,
    objeto TEXT NOT NULL,
    valor_estimado REAL,
    data_publicacao TEXT,
    data_abertura TEXT,
    data_encerramento TEXT,
    modalidade TEXT,
    modalidade_cod INTEGER,
    link_edital TEXT,
    uf TEXT,
    municipio TEXT,
    fonte TEXT DEFAULT 'pncp',

    -- Agente 1
    score_relevancia INTEGER,
    justificativa_score TEXT,
    empresa_sugerida TEXT,
    status TEXT DEFAULT 'novo',

    -- Agente 2
    analise_json TEXT,
    parecer TEXT,
    motivo_nogo TEXT,
    requisitos_habilitacao TEXT,

    -- Agente 3
    planilha_path TEXT,
    valor_proposta REAL,
    margem_percentual REAL,
    bdi_percentual REAL,

    -- Agente 4
    analise_competitiva_json TEXT,
    lance_sugerido_min REAL,
    lance_sugerido_max REAL,

    -- Telegram
    enviado_telegram INTEGER DEFAULT 0,
    telegram_message_id INTEGER,

    -- Portal
    uasg TEXT,
    portal TEXT,

    -- Metadados
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_editais_status ON editais(status);
CREATE INDEX IF NOT EXISTS idx_editais_uf ON editais(uf);
CREATE INDEX IF NOT EXISTS idx_editais_score ON editais(score_relevancia);
CREATE INDEX IF NOT EXISTS idx_editais_pncp_id ON editais(pncp_id);

-- Histórico de lances (Agente 4)
CREATE TABLE IF NOT EXISTS historico_lances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pncp_id_compra TEXT NOT NULL,
    cnpj_fornecedor TEXT NOT NULL,
    nome_fornecedor TEXT,
    valor_lance REAL,
    valor_proposta_final REAL,
    vencedor BOOLEAN DEFAULT 0,
    data_sessao TEXT,
    objeto_resumo TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_lances_cnpj ON historico_lances(cnpj_fornecedor);
CREATE INDEX IF NOT EXISTS idx_lances_compra ON historico_lances(pncp_id_compra);

-- CCTs cadastradas
CREATE TABLE IF NOT EXISTS ccts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sindicato TEXT NOT NULL,
    uf TEXT NOT NULL,
    vigencia_inicio TEXT,
    vigencia_fim TEXT,
    numero_registro TEXT,
    dados_json TEXT NOT NULL,
    ativa BOOLEAN DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Concorrentes monitorados
CREATE TABLE IF NOT EXISTS concorrentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj TEXT UNIQUE NOT NULL,
    razao_social TEXT,
    nome_fantasia TEXT,
    segmentos TEXT,
    uf_atuacao TEXT,
    notas TEXT,
    ativo BOOLEAN DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Log de execuções dos agentes
CREATE TABLE IF NOT EXISTS execucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agente TEXT NOT NULL,
    pncp_id TEXT,
    status TEXT NOT NULL,
    duracao_seg REAL,
    tokens_usados INTEGER,
    custo_estimado REAL,
    erro_msg TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Controle de estado do monitor
CREATE TABLE IF NOT EXISTS monitor_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    ultima_consulta TEXT,
    total_editais_processados INTEGER DEFAULT 0,
    ativo BOOLEAN DEFAULT 1
);

-- Comentários/chat por edital
CREATE TABLE IF NOT EXISTS comentarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pncp_id TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'anotacao',
    texto TEXT NOT NULL,
    autor TEXT DEFAULT 'Sistema',
    nivel TEXT DEFAULT 'normal',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_comentarios_pncp ON comentarios(pncp_id);

-- Tenants (SaaS multi-tenant)
CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_empresa TEXT NOT NULL,
    cnpj TEXT UNIQUE,
    email TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    plano TEXT DEFAULT 'free',
    ativo BOOLEAN DEFAULT 1,
    aprovado INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tenant_empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    cnpj TEXT,
    regime_tributario TEXT DEFAULT 'lucro_real',
    desonerada BOOLEAN DEFAULT 0,
    cprb_pct REAL DEFAULT 4.5,
    rat_pct REAL DEFAULT 3.0,
    fap REAL DEFAULT 1.0,
    rat_ajustado_pct REAL DEFAULT 3.0,
    pis_efetivo_pct REAL DEFAULT 1.65,
    cofins_efetivo_pct REAL DEFAULT 7.6,
    servicos_json TEXT DEFAULT '[]',
    atestados_json TEXT DEFAULT '[]',
    cnaes_json TEXT DEFAULT '[]',
    uf_atuacao_json TEXT DEFAULT '["RJ"]',
    restricoes_json TEXT DEFAULT '{}',
    ativo BOOLEAN DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tenant_empresas_tenant ON tenant_empresas(tenant_id);

CREATE TABLE IF NOT EXISTS pregoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pncp_id TEXT NOT NULL,
    status TEXT DEFAULT 'agendado',
    data_sessao TEXT,
    hora_sessao TEXT,
    portal TEXT DEFAULT 'comprasnet',
    link_portal TEXT,
    nossa_empresa TEXT,
    valor_proposta REAL,
    lance_final REAL,
    posicao_final INTEGER,
    total_participantes INTEGER,
    vencedor_nome TEXT,
    vencedor_valor REAL,
    resultado TEXT,
    habilitacao_status TEXT,
    recursos_prazo TEXT,
    homologacao_data TEXT,
    contrato_numero TEXT,
    contrato_vigencia_inicio TEXT,
    contrato_vigencia_fim TEXT,
    observacoes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pncp_id) REFERENCES editais(pncp_id)
);

CREATE TABLE IF NOT EXISTS lances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pregao_id INTEGER NOT NULL,
    rodada INTEGER DEFAULT 1,
    empresa TEXT,
    valor REAL,
    horario TEXT,
    tipo TEXT DEFAULT 'lance',
    nosso INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pregao_id) REFERENCES pregoes(id)
);

CREATE TABLE IF NOT EXISTS chat_pregao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pregao_id INTEGER NOT NULL,
    remetente TEXT DEFAULT 'pregoeiro',
    mensagem TEXT,
    horario TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pregao_id) REFERENCES pregoes(id)
);

CREATE TABLE IF NOT EXISTS pregao_eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pregao_id INTEGER NOT NULL,
    tipo TEXT,
    descricao TEXT,
    data_hora TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pregao_id) REFERENCES pregoes(id)
);

CREATE TABLE IF NOT EXISTS pregao_classificacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pregao_id INTEGER NOT NULL,
    posicao INTEGER NOT NULL,
    empresa TEXT NOT NULL,
    cnpj TEXT,
    valor_proposta REAL,
    valor_lance_final REAL,
    desconto_pct REAL,
    habilitado INTEGER DEFAULT 1,
    observacao TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pregao_id) REFERENCES pregoes(id)
);
"""


def init_db():
    """Cria todas as tabelas se não existirem."""
    conn = get_db()
    conn.executescript(SCHEMA_SQL)
    # Garante singleton do monitor_state
    conn.execute(
        "INSERT OR IGNORE INTO monitor_state (id, ativo) VALUES (1, 1)"
    )
    conn.commit()


# ── CRUD: Editais ─────────────────────────────────────────────────────

def upsert_edital(data: dict) -> int:
    """Insert or update edital por pncp_id. Retorna rowid."""
    conn = get_db()
    now = datetime.now().isoformat()

    existing = conn.execute(
        "SELECT id FROM editais WHERE pncp_id = ?", (data["pncp_id"],)
    ).fetchone()

    if existing:
        sets = []
        vals = []
        for k, v in data.items():
            if k == "pncp_id":
                continue
            sets.append(f"{k} = ?")
            vals.append(v)
        sets.append("updated_at = ?")
        vals.append(now)
        vals.append(data["pncp_id"])
        conn.execute(
            f"UPDATE editais SET {', '.join(sets)} WHERE pncp_id = ?", vals
        )
        conn.commit()
        return existing["id"]
    else:
        cols = list(data.keys()) + ["created_at", "updated_at"]
        placeholders = ", ".join(["?"] * len(cols))
        vals = list(data.values()) + [now, now]
        cur = conn.execute(
            f"INSERT INTO editais ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )
        conn.commit()
        return cur.lastrowid


def get_edital(pncp_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM editais WHERE pncp_id = ?", (pncp_id,)
    ).fetchone()
    return dict(row) if row else None


def get_editais_pendentes(status: str = "novo", limit: int = 50) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM editais WHERE status = ? ORDER BY created_at DESC LIMIT ?",
        (status, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_editais_recentes(limit: int = 100) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM editais ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def atualizar_status_edital(pncp_id: str, status: str, **extras):
    conn = get_db()
    sets = ["status = ?", "updated_at = ?"]
    vals = [status, datetime.now().isoformat()]
    for k, v in extras.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    vals.append(pncp_id)
    conn.execute(
        f"UPDATE editais SET {', '.join(sets)} WHERE pncp_id = ?", vals
    )
    conn.commit()


def contar_editais_por_status() -> dict:
    conn = get_db()
    rows = conn.execute(
        "SELECT status, COUNT(*) as total FROM editais GROUP BY status"
    ).fetchall()
    return {r["status"]: r["total"] for r in rows}


# ── CRUD: Histórico de Lances ─────────────────────────────────────────

def inserir_lance(data: dict):
    conn = get_db()
    cols = list(data.keys())
    placeholders = ", ".join(["?"] * len(cols))
    conn.execute(
        f"INSERT INTO historico_lances ({', '.join(cols)}) VALUES ({placeholders})",
        list(data.values()),
    )
    conn.commit()


def get_lances_por_cnpj(cnpj: str, limit: int = 50) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM historico_lances WHERE cnpj_fornecedor = ? ORDER BY data_sessao DESC LIMIT ?",
        (cnpj, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_lances_por_compra(pncp_id: str) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM historico_lances WHERE pncp_id_compra = ? ORDER BY valor_lance ASC",
        (pncp_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── CRUD: CCTs ─────────────────────────────────────────────────────────

def upsert_cct(sindicato: str, uf: str, dados_json: dict, **extras) -> int:
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM ccts WHERE sindicato = ? AND uf = ? AND ativa = 1",
        (sindicato, uf),
    ).fetchone()

    json_str = json.dumps(dados_json, ensure_ascii=False)

    if existing:
        sets = ["dados_json = ?"]
        vals = [json_str]
        for k, v in extras.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(existing["id"])
        conn.execute(f"UPDATE ccts SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
        return existing["id"]
    else:
        cols = ["sindicato", "uf", "dados_json"] + list(extras.keys())
        vals = [sindicato, uf, json_str] + list(extras.values())
        placeholders = ", ".join(["?"] * len(cols))
        cur = conn.execute(
            f"INSERT INTO ccts ({', '.join(cols)}) VALUES ({placeholders})", vals
        )
        conn.commit()
        return cur.lastrowid


def get_cct_ativa(sindicato: str, uf: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM ccts WHERE sindicato = ? AND uf = ? AND ativa = 1",
        (sindicato, uf),
    ).fetchone()
    if row:
        d = dict(row)
        d["dados"] = json.loads(d["dados_json"])
        return d
    return None


def listar_ccts_ativas() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, sindicato, uf, vigencia_inicio, vigencia_fim FROM ccts WHERE ativa = 1"
    ).fetchall()
    return [dict(r) for r in rows]


# ── CRUD: Concorrentes ─────────────────────────────────────────────────

def upsert_concorrente(cnpj: str, **data) -> int:
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM concorrentes WHERE cnpj = ?", (cnpj,)
    ).fetchone()

    if existing:
        sets = []
        vals = []
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(cnpj)
        conn.execute(
            f"UPDATE concorrentes SET {', '.join(sets)} WHERE cnpj = ?", vals
        )
        conn.commit()
        return existing["id"]
    else:
        cols = ["cnpj"] + list(data.keys())
        vals = [cnpj]
        for v in data.values():
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            vals.append(v)
        placeholders = ", ".join(["?"] * len(cols))
        cur = conn.execute(
            f"INSERT INTO concorrentes ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )
        conn.commit()
        return cur.lastrowid


def listar_concorrentes(ativos: bool = True) -> list[dict]:
    conn = get_db()
    sql = "SELECT * FROM concorrentes"
    if ativos:
        sql += " WHERE ativo = 1"
    rows = conn.execute(sql).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        for field in ("segmentos", "uf_atuacao"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        result.append(d)
    return result


# ── Log de Execuções ───────────────────────────────────────────────────

def registrar_execucao(
    agente: str,
    pncp_id: str | None,
    status: str,
    duracao_seg: float = 0,
    tokens_usados: int = 0,
    custo_estimado: float = 0,
    erro_msg: str | None = None,
):
    conn = get_db()
    conn.execute(
        """INSERT INTO execucoes (agente, pncp_id, status, duracao_seg, tokens_usados, custo_estimado, erro_msg)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (agente, pncp_id, status, duracao_seg, tokens_usados, custo_estimado, erro_msg),
    )
    conn.commit()


def get_execucoes_recentes(agente: str = None, limit: int = 20) -> list[dict]:
    conn = get_db()
    if agente:
        rows = conn.execute(
            "SELECT * FROM execucoes WHERE agente = ? ORDER BY created_at DESC LIMIT ?",
            (agente, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM execucoes ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_custo_total(dias: int = 30) -> float:
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(custo_estimado), 0) as total FROM execucoes WHERE created_at >= datetime('now', ?)",
        (f"-{dias} days",),
    ).fetchone()
    return row["total"]


# ── Monitor State ──────────────────────────────────────────────────────

def get_monitor_state() -> dict:
    conn = get_db()
    row = conn.execute("SELECT * FROM monitor_state WHERE id = 1").fetchone()
    return dict(row) if row else {"ativo": False}


def set_monitor_state(**updates):
    conn = get_db()
    sets = []
    vals = []
    for k, v in updates.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    if sets:
        conn.execute(
            f"UPDATE monitor_state SET {', '.join(sets)} WHERE id = 1", vals
        )
        conn.commit()


# ── Comentários ────────────────────────────────────────────────────────

def listar_comentarios(pncp_id: str) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM comentarios WHERE pncp_id = ? ORDER BY created_at ASC",
        (pncp_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def adicionar_comentario(pncp_id: str, texto: str, tipo: str = "anotacao", autor: str = "Sistema", nivel: str = "normal") -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO comentarios (pncp_id, tipo, texto, autor, nivel) VALUES (?, ?, ?, ?, ?)",
        (pncp_id, tipo, texto, autor, nivel),
    )
    conn.commit()
    return cur.lastrowid


# ── CRUD: Tenants (SaaS) ──────────────────────────────────────────────

def criar_tenant(nome_empresa: str, email: str, senha_hash: str, cnpj: str = None) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tenants (nome_empresa, cnpj, email, senha_hash) VALUES (?, ?, ?, ?)",
        (nome_empresa, cnpj, email, senha_hash),
    )
    conn.commit()
    return cur.lastrowid


def get_tenant_by_email(email: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM tenants WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_tenant(tenant_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    return dict(row) if row else None


# ── CRUD: Tenant Empresas ──────────────────────────────────────────────

def criar_tenant_empresa(tenant_id: int, data: dict) -> int:
    conn = get_db()
    cols = ["tenant_id"] + list(data.keys())
    vals = [tenant_id] + [
        json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
        for v in data.values()
    ]
    placeholders = ", ".join(["?"] * len(cols))
    cur = conn.execute(
        f"INSERT INTO tenant_empresas ({', '.join(cols)}) VALUES ({placeholders})", vals
    )
    conn.commit()
    return cur.lastrowid


def get_tenant_empresas(tenant_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tenant_empresas WHERE tenant_id = ? AND ativo = 1", (tenant_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        for field in ("servicos_json", "atestados_json", "cnaes_json", "uf_atuacao_json", "restricoes_json"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        result.append(d)
    return result


def atualizar_tenant_empresa(empresa_id: int, data: dict):
    conn = get_db()
    sets = []
    vals = []
    for k, v in data.items():
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k} = ?")
        vals.append(v)
    vals.append(empresa_id)
    conn.execute(f"UPDATE tenant_empresas SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()


def deletar_tenant_empresa(empresa_id: int):
    conn = get_db()
    conn.execute("UPDATE tenant_empresas SET ativo = 0 WHERE id = ?", (empresa_id,))
    conn.commit()
