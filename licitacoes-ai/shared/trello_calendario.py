"""Sincroniza os editais de cada empresa-tenant como cards no Trello (vista Calendário).

Cada empresa tem o seu board (api_key/token/board_id em tenant_empresas). O sync é
IDEMPOTENTE: usa editais.trello_card_id pra ATUALIZAR o card em vez de duplicar.
Roda sob demanda (botão/endpoint) e 1x/dia (thread no startup da API).
"""
import json
import logging
import os
import re
from datetime import datetime

import httpx

from shared.database import get_db

log = logging.getLogger("trello_calendario")
TRELLO = "https://api.trello.com/1"
TIMEOUT = 20


def _parse_due(valor) -> str | None:
    """Normaliza a data de encerramento pra ISO 8601 (aceito pelo Trello). None se inválida."""
    if not valor:
        return None
    s = str(valor).strip().replace("Z", "")
    try:
        return datetime.fromisoformat(s).isoformat()
    except ValueError:
        pass
    for f in ("%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, f).isoformat()
        except ValueError:
            continue
    return None


_DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
# Nomes default do Trello (PT/EN) — listas vazias assim são arquivadas no fim.
_LISTAS_DEFAULT = {"to do", "doing", "done", "a fazer", "fazendo", "feito", "lista", "pendências",
                   "em andamento", "concluído", "concluido", "tarefas", "backlog"}


def _label_dia(due_iso: str):
    """('2026-06-26T09:00:00') -> (datetime, '26/06 (sex)'). Uma lista por dia."""
    d = datetime.fromisoformat(due_iso)
    return d, f"{d.day:02d}/{d.month:02d} ({_DIAS[d.weekday()]})"


def _carregar_listas(board: str, auth: dict) -> list[dict]:
    return httpx.get(
        f"{TRELLO}/boards/{board}/lists",
        params={**auth, "filter": "open", "fields": "id,name"}, timeout=TIMEOUT,
    ).json()


def _lista_do_dia(board: str, auth: dict, nome: str, pos: int, cache: dict) -> str:
    """Acha (ou cria) a lista daquele dia. `pos` = ordinal da data → ordem cronológica."""
    if nome in cache:
        return cache[nome]
    nova = httpx.post(
        f"{TRELLO}/lists",
        params={**auth, "idBoard": board, "name": nome, "pos": pos}, timeout=TIMEOUT,
    ).json()
    cache[nome] = nova["id"]
    return nova["id"]


def _arquivar_listas_default_vazias(board: str, auth: dict):
    """Arquiva as listas default (To Do/Doing/Done…) quando ficam vazias após o sync.

    NUNCA toca numa lista de dia (padrão dd/mm) — blindagem dupla.
    """
    for l in _carregar_listas(board, auth):
        nome = (l.get("name") or "")
        if re.match(r"^\d{2}/\d{2}", nome):       # lista de dia → jamais arquiva
            continue
        if nome.lower() not in _LISTAS_DEFAULT:
            continue
        cards = httpx.get(f"{TRELLO}/lists/{l['id']}/cards",
                          params={**auth, "fields": "id"}, timeout=TIMEOUT).json()
        if not cards:
            httpx.put(f"{TRELLO}/lists/{l['id']}/closed",
                      params={**auth, "value": "true"}, timeout=TIMEOUT)


def _carregar_analise(ed: dict) -> dict:
    """Lê o analise_json do edital (saída do agente analista/precificador)."""
    raw = ed.get("analise_json")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _parecer(ed: dict, analise: dict):
    """Resume o veredito da IA num (emoji, rótulo, cor de label)."""
    p = str(ed.get("parecer") or analise.get("parecer") or "").lower().replace("-", "").replace("_", "")
    st = str(ed.get("status") or "").lower()
    if p.startswith("nogo") or st == "nogo":
        return "❌", "NÃO-GO", "red"
    if p.startswith("go") or st in ("go", "go_com_ressalvas", "go_sem_ressalvas"):
        return "✅", "GO", "green"
    if st in ("precificado", "analisado", "competitivo_pronto"):
        return "🔵", "AVALIAR", "blue"
    return "🟡", "NOVO", "yellow"


def _brl(v) -> str:
    """Formata no padrão brasileiro: 7025.88 -> '7.025,88'."""
    try:
        return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(v)


def _descricao_mastigada(ed: dict, analise: dict, emoji: str, rotulo: str) -> str:
    """Monta a descrição 'mastigada' do card com a análise dos agentes de IA."""
    teto = ed.get("valor_estimado") or analise.get("valor_estimado") or 0
    proposta = ed.get("valor_proposta") or 0
    score = ed.get("score_relevancia")
    resumo = analise.get("resumo") or (ed.get("objeto") or "")[:160]

    L = [f"## {emoji} PARECER: {rotulo}" + (f"  ·  Score {score}/100" if score else "")]
    L.append("")
    L.append(f"**📋 Objeto:** {resumo}")
    val = f"**💰 Teto:** R$ {_brl(teto)}"
    if proposta:
        margem = f" ({(1 - proposta/teto)*100:.1f}% abaixo)" if teto else ""
        val += f"  →  **Nossa proposta:** R$ {_brl(proposta)}{margem}"
    L.append(val)

    flags = []
    if analise.get("criterio"):
        flags.append(f"Critério: {analise['criterio']}")
    if analise.get("me_epp_exclusivo"):
        flags.append("⭐ EXCLUSIVO ME/EPP")
    if analise.get("exige_atestado"):
        flags.append("⚠️ Exige atestado")
    if analise.get("prazo_entrega_dias"):
        flags.append(f"Entrega {analise['prazo_entrega_dias']}d")
    if analise.get("garantia_meses"):
        flags.append(f"Garantia {analise['garantia_meses']}m")
    if flags:
        L.append("**🏷️ " + "  ·  ".join(flags) + "**")

    L.append("")
    local = ed.get("uf", "") + (f" / {ed['municipio']}" if ed.get("municipio") else "")
    L.append(f"**🏛️ Órgão:** {ed.get('orgao_nome','')}  ({local})")
    L.append(f"**📅 Abertura:** {ed.get('data_abertura','-')}  ·  **Encerra:** {ed.get('data_encerramento','-')}")
    if ed.get("planilha_path"):
        L.append("**📊 Planilha de preço:** já gerada ✅")
    L.append("")
    if ed.get("link_edital"):
        L.append(f"🔗 {ed['link_edital']}")
    L.append(f"`{ed.get('pncp_id')}`")
    return "\n".join(L)


def _label_id(board: str, auth: dict, texto: str, cor: str, cache: dict) -> str | None:
    """Acha/cria a label de parecer (✅GO verde / ❌NÃO vermelho / etc.). Idempotente."""
    if not cache.get("_loaded"):
        try:
            for l in httpx.get(f"{TRELLO}/boards/{board}/labels",
                               params={**auth, "fields": "id,name,color"}, timeout=TIMEOUT).json():
                cache[f"{l.get('name')}|{l.get('color')}"] = l["id"]
        except Exception:
            pass
        cache["_loaded"] = True
    key = f"{texto}|{cor}"
    if key in cache:
        return cache[key]
    try:
        nova = httpx.post(f"{TRELLO}/labels",
                          params={**auth, "idBoard": board, "name": texto, "color": cor}, timeout=TIMEOUT).json()
        cache[key] = nova["id"]
        return nova["id"]
    except Exception:
        return None


# tipo_negocio do onboarding → chave do canal Telegram do nicho (cada um tem bot+grupo próprios)
_MAP_NICHO_CANAL = {
    "aquisicao": "aquisicao_ti",
    "mao_obra": "mdo",
    "obras": "obra",
    "residuos": "residuos",
}


def _enviar_telegram(token: str, chat_id: str, texto: str) -> bool:
    """Manda mensagem pro Telegram com o bot/chat informados. Silencioso se faltar."""
    if not (token and chat_id):
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": texto, "parse_mode": "HTML",
                  "disable_web_page_preview": True}, timeout=15,
        )
        if r.status_code == 200:
            return True
        log.warning(f"Telegram {r.status_code}: {r.text[:150]}")
        return False
    except Exception as e:
        log.warning(f"Telegram: {e}")
        return False


def _canal_do_tenant(empresa: dict, tenant_id: int):
    """Resolve (bot_token, chat_id) do canal certo: nicho do tenant > override da empresa > global."""
    try:
        from shared.nichos import rota_por_nicho
        row = get_db().execute("SELECT tipo_negocio FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        tipo = (dict(row).get("tipo_negocio") if row else "") or ""
        nicho = _MAP_NICHO_CANAL.get(tipo, tipo)
        rota = rota_por_nicho(nicho) if nicho else None
        if rota:
            return rota.token, rota.chat_id
    except Exception as e:
        log.warning(f"Rota de nicho: {e}")
    # override por empresa (usa o bot global) / fallback global
    g = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = empresa.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
    return g, chat


def _enviar_digest(empresa: dict, tenant_id: int, board: str, auth: dict) -> bool:
    """Digest no Telegram: o que vence HOJE + visão da semana (GO/NÃO), no canal do nicho."""
    token, chat = _canal_do_tenant(empresa, tenant_id)
    if not (token and chat):
        return False
    hoje = datetime.now().date()
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM editais WHERE tenant_id = ? AND COALESCE(status,'') NOT IN ('arquivado')
             AND COALESCE(data_encerramento,'') != ''""", (tenant_id,),
    ).fetchall()

    hoje_list, semana, ngo, nnao, noutros = [], 0, 0, 0, 0
    for r in rows:
        ed = dict(r)
        due = _parse_due(ed.get("data_encerramento"))
        if not due:
            continue
        d = datetime.fromisoformat(due).date()
        dias = (d - hoje).days
        analise = _carregar_analise(ed)
        emoji, rot, _ = _parecer(ed, analise)
        if rot == "GO":
            ngo += 1
        elif rot.startswith("NÃO"):
            nnao += 1
        else:
            noutros += 1
        if 0 <= dias <= 7:
            semana += 1
        if dias == 0:
            hh = datetime.fromisoformat(due).strftime("%H:%M")
            teto = ed.get("valor_estimado") or 0
            hoje_list.append(
                f"{emoji} [{ed.get('uf','?')}] {(ed.get('orgao_nome') or '')[:34]} — R$ {_brl(teto).split(',')[0]} ({hh})"
            )

    try:
        burl = httpx.get(f"{TRELLO}/boards/{board}", params={**auth, "fields": "shortUrl"}, timeout=10).json().get("shortUrl", "")
    except Exception:
        burl = ""

    msg = f"📅 <b>Calendário Licitações — {empresa.get('nome','')}</b>\n\n"
    msg += f"🔴 <b>HOJE ({hoje.strftime('%d/%m')}): {len(hoje_list)} prazo(s)</b>\n"
    msg += ("\n".join(hoje_list[:10]) if hoje_list else "— nada vence hoje")
    msg += f"\n\n📆 Próximos 7 dias: <b>{semana}</b>\n"
    msg += f"✅ GO: {ngo}   ❌ NÃO: {nnao}   🟡 Avaliar: {noutros}"
    if burl:
        msg += f"\n\n🔗 Abrir calendário: {burl}"
    return _enviar_telegram(token, chat, msg)


def sincronizar_calendario(empresa: dict, tenant_id: int, avisar_telegram: bool = True) -> dict:
    """Cria/atualiza um card por edital (com prazo) no board da empresa. Idempotente."""
    k, t, board = empresa.get("trello_api_key"), empresa.get("trello_token"), empresa.get("trello_board_id")
    if not (k and t and board):
        return {"ok": False, "erro": "Trello não configurado (api_key/token/board_id)"}
    auth = {"key": k, "token": t}
    try:
        cache_listas = {l["name"]: l["id"] for l in _carregar_listas(board, auth)}
    except Exception as e:
        return {"ok": False, "erro": f"Falha ao acessar o board: {e}"}

    cache_labels = {}
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM editais
           WHERE tenant_id = ? AND COALESCE(status,'') NOT IN ('arquivado')
             AND COALESCE(data_encerramento,'') != ''""",
        (tenant_id,),
    ).fetchall()

    criados = atualizados = ignorados = erros = 0
    for r in rows:
        ed = dict(r)
        due = _parse_due(ed.get("data_encerramento"))
        if not due:
            ignorados += 1
            continue
        # Lista do DIA do vencimento (uma por dia, em ordem cronológica).
        dt, label_dia = _label_dia(due)
        try:
            lista_id = _lista_do_dia(board, auth, label_dia, dt.toordinal(), cache_listas)
        except Exception as e:
            log.warning(f"Lista do dia {label_dia}: {e}")
            erros += 1
            continue
        analise = _carregar_analise(ed)
        emoji, rotulo, cor = _parecer(ed, analise)
        teto = ed.get("valor_estimado") or analise.get("valor_estimado") or 0
        nome = f"{emoji} [{ed.get('uf','?')}] {(ed.get('orgao_nome') or '')[:42]} · R$ {_brl(teto).split(',')[0]}"
        desc = _descricao_mastigada(ed, analise, emoji, rotulo)
        lbl = _label_id(board, auth, f"{emoji} {rotulo}", cor, cache_labels)

        base = {**auth, "name": nome, "desc": desc, "due": due, "idList": lista_id}
        if lbl:
            base["idLabels"] = lbl

        card_id = ed.get("trello_card_id")
        try:
            if card_id:
                resp = httpx.put(f"{TRELLO}/cards/{card_id}", params=base, timeout=TIMEOUT)
                if resp.status_code == 200:
                    atualizados += 1
                    continue
                if resp.status_code == 404:
                    card_id = None  # card apagado no Trello → recria
                else:
                    erros += 1
                    continue
            resp = httpx.post(
                f"{TRELLO}/cards", params={**base, "pos": "bottom"}, timeout=TIMEOUT,
            )
            if resp.status_code in (200, 201):
                conn.execute(
                    "UPDATE editais SET trello_card_id = ?, tenant_empresa_id = ? WHERE pncp_id = ?",
                    (resp.json()["id"], empresa["id"], ed["pncp_id"]),
                )
                criados += 1
            else:
                erros += 1
        except Exception as e:
            log.warning(f"Card edital {ed.get('pncp_id')}: {e}")
            erros += 1

    conn.commit()
    try:
        _arquivar_listas_default_vazias(board, auth)
    except Exception as e:
        log.warning(f"Arquivar listas default: {e}")

    telegram_ok = False
    if avisar_telegram:
        try:
            telegram_ok = _enviar_digest(empresa, tenant_id, board, auth)
        except Exception as e:
            log.warning(f"Digest Telegram: {e}")

    return {
        "ok": True, "total": len(rows), "criados": criados, "atualizados": atualizados,
        "ignorados_sem_data": ignorados, "erros": erros, "telegram": telegram_ok,
    }


def sincronizar_todas() -> dict:
    """Sincroniza o calendário de TODAS as empresas com Trello configurado (job diário)."""
    conn = get_db()
    empresas = conn.execute(
        """SELECT * FROM tenant_empresas
           WHERE ativo = 1 AND COALESCE(trello_api_key,'') != ''
             AND COALESCE(trello_token,'') != '' AND COALESCE(trello_board_id,'') != ''"""
    ).fetchall()
    detalhe = []
    for e in empresas:
        emp = dict(e)
        res = sincronizar_calendario(emp, emp["tenant_id"])
        detalhe.append({"empresa_id": emp["id"], "nome": emp.get("nome"), **res})
        log.info(f"Trello sync empresa {emp['id']} ({emp.get('nome')}): {res}")
    return {"empresas": len(detalhe), "detalhe": detalhe}
