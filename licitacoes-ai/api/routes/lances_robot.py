"""Robô de disputa — cálculo e registro de lances automáticos."""
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from api.deps import get_connection

router = APIRouter(prefix="/api/pregoes", tags=["robot"])


# ── Models ──

class RobotConfig(BaseModel):
    modo: str = "semi_auto"  # semi_auto | auto
    estrategia: str = "conservador"  # conservador | agressivo | espelho | decremental | piso
    valor_minimo: float = 0
    desconto_maximo_pct: float = 25
    intervalo_lances_seg: int = 10
    empresa: str = "MANUTEC"
    notificar_telegram: bool = True


class LanceRegistro(BaseModel):
    valor: float
    valor_anterior: float = 0
    posicao_antes: int = 0
    posicao_depois: int = 0
    estrategia_usada: str = ""
    modo: str = "manual"  # manual | semi_auto | auto
    portal: str = "comprasgov"
    sucesso: bool = True
    erro: Optional[str] = None


# ── Tabela do robô ──

def _ensure_robot_tables():
    conn = get_connection()
    conn.execute("""CREATE TABLE IF NOT EXISTS robot_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pregao_id INTEGER NOT NULL UNIQUE,
        modo TEXT DEFAULT 'semi_auto',
        estrategia TEXT DEFAULT 'conservador',
        valor_minimo REAL DEFAULT 0,
        desconto_maximo_pct REAL DEFAULT 25,
        intervalo_lances_seg INTEGER DEFAULT 10,
        empresa TEXT DEFAULT 'MANUTEC',
        notificar_telegram INTEGER DEFAULT 1,
        ativo INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (pregao_id) REFERENCES pregoes(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS robot_lances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pregao_id INTEGER NOT NULL,
        valor REAL NOT NULL,
        valor_anterior REAL,
        posicao_antes INTEGER,
        posicao_depois INTEGER,
        estrategia_usada TEXT,
        modo TEXT DEFAULT 'manual',
        portal TEXT DEFAULT 'comprasgov',
        sucesso INTEGER DEFAULT 1,
        erro TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (pregao_id) REFERENCES pregoes(id)
    )""")
    conn.commit()


# ── Estratégias de lance ──

def _calcular_lance_conservador(valor_atual_lider, valor_estimado, valor_minimo):
    """Cobre o líder com margem de 0.5%."""
    lance = valor_atual_lider * 0.995
    return max(lance, valor_minimo)


def _calcular_lance_agressivo(valor_atual_lider, valor_estimado, valor_minimo):
    """Vai direto ao valor mínimo rentável."""
    # Piso = break-even + 3% margem
    piso_seguro = valor_minimo * 1.03 if valor_minimo > 0 else valor_atual_lider * 0.85
    lance = min(valor_atual_lider * 0.99, piso_seguro)
    return max(lance, valor_minimo)


def _calcular_lance_espelho(valor_atual_lider, valor_estimado, valor_minimo):
    """Copia valor do líder - R$ 1."""
    lance = valor_atual_lider - 1
    return max(lance, valor_minimo)


def _calcular_lance_decremental(valor_atual_lider, valor_estimado, valor_minimo, rodada=1):
    """Reduz 1% por rodada."""
    pct = min(0.01 * rodada, 0.15)  # max 15%
    lance = valor_atual_lider * (1 - pct)
    return max(lance, valor_minimo)


def _calcular_lance_piso(valor_atual_lider, valor_estimado, valor_minimo):
    """Vai direto ao piso de inexequibilidade + 1%."""
    piso_inexeq = valor_estimado * 0.75 if valor_estimado > 0 else valor_atual_lider * 0.75
    lance = piso_inexeq * 1.01
    return max(lance, valor_minimo)


ESTRATEGIAS = {
    "conservador": _calcular_lance_conservador,
    "agressivo": _calcular_lance_agressivo,
    "espelho": _calcular_lance_espelho,
    "decremental": _calcular_lance_decremental,
    "piso": _calcular_lance_piso,
}


# ── Rotas ──

@router.post("/{pregao_id}/robot/configurar")
def configurar_robot(pregao_id: int, body: RobotConfig):
    """Configura estratégia do robô para um pregão."""
    _ensure_robot_tables()
    conn = get_connection()

    existing = conn.execute("SELECT id FROM robot_config WHERE pregao_id = ?", (pregao_id,)).fetchone()
    if existing:
        conn.execute("""UPDATE robot_config SET modo=?, estrategia=?, valor_minimo=?, desconto_maximo_pct=?,
            intervalo_lances_seg=?, empresa=?, notificar_telegram=?, ativo=1, updated_at=datetime('now')
            WHERE pregao_id=?""",
            (body.modo, body.estrategia, body.valor_minimo, body.desconto_maximo_pct,
             body.intervalo_lances_seg, body.empresa, 1 if body.notificar_telegram else 0, pregao_id))
    else:
        conn.execute("""INSERT INTO robot_config (pregao_id, modo, estrategia, valor_minimo, desconto_maximo_pct,
            intervalo_lances_seg, empresa, notificar_telegram)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pregao_id, body.modo, body.estrategia, body.valor_minimo, body.desconto_maximo_pct,
             body.intervalo_lances_seg, body.empresa, 1 if body.notificar_telegram else 0))
    conn.commit()
    return {"ok": True, "config": body.model_dump()}


@router.get("/{pregao_id}/robot/status")
def status_robot(pregao_id: int):
    """Retorna configuração e histórico do robô."""
    _ensure_robot_tables()
    conn = get_connection()

    config = conn.execute("SELECT * FROM robot_config WHERE pregao_id = ?", (pregao_id,)).fetchone()
    lances = conn.execute("SELECT * FROM robot_lances WHERE pregao_id = ? ORDER BY id DESC LIMIT 20", (pregao_id,)).fetchall()
    pregao = conn.execute("SELECT * FROM pregoes WHERE id = ?", (pregao_id,)).fetchone()

    return {
        "config": dict(config) if config else None,
        "lances_robot": [dict(l) for l in lances],
        "pregao_status": pregao["status"] if pregao else None,
        "ativo": bool(config and config["ativo"]) if config else False,
    }


@router.post("/{pregao_id}/robot/calcular")
async def calcular_lance(pregao_id: int, request: Request):
    """Calcula próximo lance ideal baseado na estratégia configurada."""
    _ensure_robot_tables()
    conn = get_connection()

    body = await request.json()
    valor_atual_lider = body.get("valor_atual_lider", 0)
    nossa_posicao = body.get("nossa_posicao", 0)
    nosso_lance_atual = body.get("nosso_lance_atual", 0)
    total_participantes = body.get("total_participantes", 0)
    rodada = body.get("rodada", 1)

    # Busca config
    config = conn.execute("SELECT * FROM robot_config WHERE pregao_id = ?", (pregao_id,)).fetchone()
    if not config:
        return {"ok": False, "error": "Robô não configurado. Use /robot/configurar primeiro."}

    # Busca valor estimado do edital
    pregao = conn.execute("""SELECT p.*, e.valor_estimado FROM pregoes p
        LEFT JOIN editais e ON p.pncp_id = e.pncp_id WHERE p.id = ?""", (pregao_id,)).fetchone()
    valor_estimado = pregao["valor_estimado"] if pregao else 0

    estrategia = config["estrategia"]
    valor_minimo = config["valor_minimo"]
    desconto_max = config["desconto_maximo_pct"]

    # Calcula desconto máximo permitido
    if valor_estimado > 0 and desconto_max > 0:
        limite_desconto = valor_estimado * (1 - desconto_max / 100)
        valor_minimo = max(valor_minimo, limite_desconto)

    # Se já somos o líder, não precisa dar lance
    if nossa_posicao == 1 and nosso_lance_atual <= valor_atual_lider:
        return {
            "ok": True,
            "acao": "manter",
            "motivo": "Já somos o líder. Manter posição.",
            "lance_sugerido": nosso_lance_atual,
            "nossa_posicao": 1,
        }

    # Calcula lance pela estratégia
    func = ESTRATEGIAS.get(estrategia, _calcular_lance_conservador)
    if estrategia == "decremental":
        lance_sugerido = func(valor_atual_lider, valor_estimado, valor_minimo, rodada)
    else:
        lance_sugerido = func(valor_atual_lider, valor_estimado, valor_minimo)

    # Arredonda para 2 casas
    lance_sugerido = round(lance_sugerido, 2)

    # Verifica limites
    piso_inexeq = valor_estimado * 0.5 if valor_estimado > 0 else 0
    abaixo_piso = lance_sugerido < piso_inexeq if piso_inexeq > 0 else False
    abaixo_minimo = lance_sugerido < valor_minimo if valor_minimo > 0 else False

    # Desconto em relação ao estimado
    desconto_pct = ((valor_estimado - lance_sugerido) / valor_estimado * 100) if valor_estimado > 0 else 0

    # Decide ação
    if abaixo_piso:
        acao = "bloquear"
        motivo = f"Lance R$ {lance_sugerido:,.2f} está abaixo do piso de inexequibilidade (R$ {piso_inexeq:,.2f}). Bloqueado."
        lance_sugerido = piso_inexeq * 1.01
    elif abaixo_minimo:
        acao = "alerta"
        motivo = f"Lance R$ {lance_sugerido:,.2f} está abaixo do valor mínimo configurado (R$ {valor_minimo:,.2f})."
        lance_sugerido = valor_minimo
    elif lance_sugerido >= nosso_lance_atual and nosso_lance_atual > 0:
        acao = "manter"
        motivo = "Lance calculado é maior ou igual ao nosso lance atual. Manter posição."
    else:
        acao = "enviar" if config["modo"] == "auto" else "confirmar"
        motivo = f"Estratégia {estrategia}: R$ {lance_sugerido:,.2f} (desconto {desconto_pct:.1f}%)"

    return {
        "ok": True,
        "acao": acao,  # enviar | confirmar | manter | bloquear | alerta
        "lance_sugerido": lance_sugerido,
        "estrategia": estrategia,
        "modo": config["modo"],
        "motivo": motivo,
        "desconto_pct": round(desconto_pct, 2),
        "valor_atual_lider": valor_atual_lider,
        "nossa_posicao_atual": nossa_posicao,
        "nosso_lance_atual": nosso_lance_atual,
        "valor_minimo": valor_minimo,
        "piso_inexequibilidade": piso_inexeq,
        "valor_estimado": valor_estimado,
    }


@router.post("/{pregao_id}/robot/registrar")
def registrar_lance_robot(pregao_id: int, body: LanceRegistro):
    """Registra lance enviado pelo robô (audit trail)."""
    _ensure_robot_tables()
    conn = get_connection()

    conn.execute("""INSERT INTO robot_lances (pregao_id, valor, valor_anterior, posicao_antes, posicao_depois,
        estrategia_usada, modo, portal, sucesso, erro)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pregao_id, body.valor, body.valor_anterior, body.posicao_antes, body.posicao_depois,
         body.estrategia_usada, body.modo, body.portal, 1 if body.sucesso else 0, body.erro))

    # Atualiza lance final no pregão
    if body.sucesso:
        conn.execute("UPDATE pregoes SET lance_final = ?, updated_at = datetime('now') WHERE id = ?",
                     (body.valor, pregao_id))

    # Registra evento
    conn.execute("INSERT INTO pregao_eventos (pregao_id, tipo, descricao, data_hora) VALUES (?, ?, ?, ?)",
        (pregao_id, "robot_lance",
         f"Lance R$ {body.valor:,.2f} enviado ({body.estrategia_usada}, {body.modo})" if body.sucesso
         else f"Lance R$ {body.valor:,.2f} FALHOU: {body.erro}",
         datetime.now().isoformat()))

    conn.commit()

    # Notifica Telegram se configurado
    config = conn.execute("SELECT notificar_telegram FROM robot_config WHERE pregao_id = ?", (pregao_id,)).fetchone()
    if config and config["notificar_telegram"]:
        _notificar_lance_telegram(pregao_id, body)

    return {"ok": True, "lance_id": conn.execute("SELECT last_insert_rowid()").fetchone()[0]}


@router.post("/{pregao_id}/robot/parar")
def parar_robot(pregao_id: int):
    """Desativa o robô para este pregão."""
    _ensure_robot_tables()
    conn = get_connection()
    conn.execute("UPDATE robot_config SET ativo = 0, updated_at = datetime('now') WHERE pregao_id = ?", (pregao_id,))
    conn.commit()
    return {"ok": True}


def _notificar_lance_telegram(pregao_id, lance):
    """Envia notificação Telegram sobre lance do robô."""
    try:
        import os
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return

        import httpx
        msg = f"🤖 *ROBÔ DE DISPUTA*\n"
        msg += f"{'✅' if lance.sucesso else '❌'} Lance: R$ {lance.valor:,.2f}\n"
        msg += f"Estratégia: {lance.estrategia_usada}\n"
        msg += f"Modo: {lance.modo}\n"
        if lance.erro:
            msg += f"Erro: {lance.erro}\n"

        httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception:
        pass
