"""Rotas de acompanhamento de pregões e pós-licitação."""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel
from api.deps import get_connection

router = APIRouter(prefix="/api/pregoes", tags=["pregoes"])


# ── Models ──

class PregaoCreate(BaseModel):
    pncp_id: str
    data_sessao: Optional[str] = None
    hora_sessao: Optional[str] = None
    portal: str = "comprasnet"
    link_portal: Optional[str] = None
    nossa_empresa: Optional[str] = None
    valor_proposta: Optional[float] = None
    observacoes: Optional[str] = None


class PregaoUpdate(BaseModel):
    status: Optional[str] = None
    lance_final: Optional[float] = None
    posicao_final: Optional[int] = None
    total_participantes: Optional[int] = None
    vencedor_nome: Optional[str] = None
    vencedor_valor: Optional[float] = None
    resultado: Optional[str] = None
    habilitacao_status: Optional[str] = None
    recursos_prazo: Optional[str] = None
    homologacao_data: Optional[str] = None
    contrato_numero: Optional[str] = None
    contrato_vigencia_inicio: Optional[str] = None
    contrato_vigencia_fim: Optional[str] = None
    observacoes: Optional[str] = None


class LanceCreate(BaseModel):
    empresa: str
    valor: float
    horario: Optional[str] = None
    rodada: int = 1
    nosso: bool = False


class ChatCreate(BaseModel):
    remetente: str = "pregoeiro"
    mensagem: str
    horario: Optional[str] = None


class EventoCreate(BaseModel):
    tipo: str
    descricao: str
    data_hora: Optional[str] = None


# ── Rotas de Pregões ──

@router.get("/")
def listar_pregoes(status: str = Query(None)):
    """Lista todos os pregões com dados do edital."""
    conn = get_connection()
    if status:
        rows = conn.execute("""
            SELECT p.*, e.orgao_nome, e.objeto, e.valor_estimado, e.uf, e.municipio
            FROM pregoes p JOIN editais e ON p.pncp_id = e.pncp_id
            WHERE p.status = ? ORDER BY p.data_sessao DESC
        """, (status,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT p.*, e.orgao_nome, e.objeto, e.valor_estimado, e.uf, e.municipio
            FROM pregoes p JOIN editais e ON p.pncp_id = e.pncp_id
            ORDER BY p.data_sessao DESC
        """).fetchall()
    return [dict(r) for r in rows]


@router.get("/stats")
def stats_pregoes():
    """Estatísticas gerais dos pregões."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM pregoes").fetchone()[0]
    agendados = conn.execute("SELECT COUNT(*) FROM pregoes WHERE status = 'agendado'").fetchone()[0]
    em_disputa = conn.execute("SELECT COUNT(*) FROM pregoes WHERE status = 'em_disputa'").fetchone()[0]
    vencidos = conn.execute("SELECT COUNT(*) FROM pregoes WHERE resultado = 'vencedor'").fetchone()[0]
    perdidos = conn.execute("SELECT COUNT(*) FROM pregoes WHERE resultado IN ('perdido', 'desclassificado', 'inabilitado')").fetchone()[0]
    homologados = conn.execute("SELECT COUNT(*) FROM pregoes WHERE status = 'homologado'").fetchone()[0]

    # Valor total vencido
    val_vencido = conn.execute("SELECT COALESCE(SUM(lance_final), 0) FROM pregoes WHERE resultado = 'vencedor'").fetchone()[0]

    return {
        "total": total,
        "agendados": agendados,
        "em_disputa": em_disputa,
        "vencidos": vencidos,
        "perdidos": perdidos,
        "homologados": homologados,
        "valor_vencido": val_vencido,
        "taxa_sucesso": round(vencidos / total * 100, 1) if total > 0 else 0,
    }


@router.post("/")
def criar_pregao(body: PregaoCreate):
    """Registra participação em um pregão."""
    conn = get_connection()
    # Verifica se edital existe e pega UASG/portal
    ed = conn.execute("SELECT pncp_id, uasg, portal, data_abertura FROM editais WHERE pncp_id = ?", (body.pncp_id,)).fetchone()
    if not ed:
        raise HTTPException(404, "Edital não encontrado")

    # Verifica se já existe pregão para este edital
    existing = conn.execute("SELECT id FROM pregoes WHERE pncp_id = ?", (body.pncp_id,)).fetchone()
    if existing:
        raise HTTPException(400, "Já existe pregão registrado para este edital")

    # Herda portal e data do edital se não informado
    portal = body.portal or ed["portal"] or "comprasnet"
    data_sessao = body.data_sessao or (ed["data_abertura"][:10] if ed["data_abertura"] else None)
    hora_sessao = body.hora_sessao or (ed["data_abertura"][11:16] if ed["data_abertura"] and len(ed["data_abertura"]) > 11 else None)

    conn.execute("""
        INSERT INTO pregoes (pncp_id, status, data_sessao, hora_sessao, portal, link_portal, nossa_empresa, valor_proposta, observacoes)
        VALUES (?, 'agendado', ?, ?, ?, ?, ?, ?, ?)
    """, (body.pncp_id, data_sessao, hora_sessao, portal, body.link_portal,
          body.nossa_empresa, body.valor_proposta, body.observacoes))
    conn.commit()

    pregao_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Registra evento
    conn.execute("INSERT INTO pregao_eventos (pregao_id, tipo, descricao, data_hora) VALUES (?, ?, ?, ?)",
                 (pregao_id, "criado", "Pregão registrado no sistema", datetime.now().isoformat()))
    conn.commit()

    return {"id": pregao_id, "status": "agendado"}


@router.get("/{pregao_id}")
def detalhe_pregao(pregao_id: int):
    """Retorna detalhes completos do pregão."""
    conn = get_connection()
    pregao = conn.execute("""
        SELECT p.*, e.orgao_nome, e.objeto, e.valor_estimado, e.uf, e.municipio, e.link_edital, e.uasg, e.portal as edital_portal, e.orgao_cnpj
        FROM pregoes p JOIN editais e ON p.pncp_id = e.pncp_id
        WHERE p.id = ?
    """, (pregao_id,)).fetchone()
    if not pregao:
        raise HTTPException(404, "Pregão não encontrado")

    lances = conn.execute("SELECT * FROM lances WHERE pregao_id = ? ORDER BY id", (pregao_id,)).fetchall()
    chat = conn.execute("SELECT * FROM chat_pregao WHERE pregao_id = ? ORDER BY id", (pregao_id,)).fetchall()
    eventos = conn.execute("SELECT * FROM pregao_eventos WHERE pregao_id = ? ORDER BY id DESC", (pregao_id,)).fetchall()
    classificacao = conn.execute("SELECT * FROM pregao_classificacao WHERE pregao_id = ? ORDER BY posicao", (pregao_id,)).fetchall()

    return {
        "pregao": dict(pregao),
        "lances": [dict(l) for l in lances],
        "chat": [dict(c) for c in chat],
        "eventos": [dict(e) for e in eventos],
        "classificacao": [dict(c) for c in classificacao],
    }


@router.put("/{pregao_id}")
def atualizar_pregao(pregao_id: int, body: PregaoUpdate):
    """Atualiza status/dados do pregão."""
    conn = get_connection()
    pregao = conn.execute("SELECT * FROM pregoes WHERE id = ?", (pregao_id,)).fetchone()
    if not pregao:
        raise HTTPException(404, "Pregão não encontrado")

    updates = []
    values = []
    for field, val in body.model_dump(exclude_none=True).items():
        updates.append(f"{field} = ?")
        values.append(val)

    if not updates:
        raise HTTPException(400, "Nenhum campo para atualizar")

    updates.append("updated_at = datetime('now')")
    values.append(pregao_id)

    conn.execute(f"UPDATE pregoes SET {', '.join(updates)} WHERE id = ?", values)

    # Registra evento de mudança de status
    if body.status:
        status_labels = {
            "agendado": "Pregão agendado",
            "em_disputa": "Sessão de disputa iniciada",
            "suspensa": "Sessão suspensa pelo pregoeiro",
            "encerrado": "Fase de lances encerrada",
            "habilitacao": "Fase de habilitação",
            "resultado": "Resultado divulgado",
            "recurso": "Em fase de recurso",
            "homologado": "Pregão homologado",
            "contrato": "Contrato assinado",
            "fracassado": "Pregão fracassado/deserto",
        }
        desc = status_labels.get(body.status, f"Status alterado para: {body.status}")
        conn.execute("INSERT INTO pregao_eventos (pregao_id, tipo, descricao, data_hora) VALUES (?, ?, ?, ?)",
                     (pregao_id, "status", desc, datetime.now().isoformat()))

    if body.resultado:
        resultado_labels = {
            "vencedor": "Empresa declarada vencedora!",
            "perdido": "Não vencemos este pregão",
            "desclassificado": "Proposta desclassificada",
            "inabilitado": "Empresa inabilitada",
        }
        desc = resultado_labels.get(body.resultado, f"Resultado: {body.resultado}")
        conn.execute("INSERT INTO pregao_eventos (pregao_id, tipo, descricao, data_hora) VALUES (?, ?, ?, ?)",
                     (pregao_id, "resultado", desc, datetime.now().isoformat()))

    conn.commit()
    return {"ok": True}


# ── Lances ──

@router.post("/{pregao_id}/lances")
def registrar_lance(pregao_id: int, body: LanceCreate):
    """Registra um lance no pregão."""
    conn = get_connection()
    horario = body.horario or datetime.now().strftime("%H:%M:%S")
    conn.execute(
        "INSERT INTO lances (pregao_id, rodada, empresa, valor, horario, nosso) VALUES (?, ?, ?, ?, ?, ?)",
        (pregao_id, body.rodada, body.empresa, body.valor, horario, 1 if body.nosso else 0))
    conn.commit()
    return {"ok": True}


@router.get("/{pregao_id}/lances")
def listar_lances(pregao_id: int):
    """Lista lances do pregão."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM lances WHERE pregao_id = ? ORDER BY id", (pregao_id,)).fetchall()
    return [dict(r) for r in rows]


# ── Chat do Pregoeiro ──

@router.post("/{pregao_id}/chat")
def registrar_mensagem(pregao_id: int, body: ChatCreate):
    """Registra mensagem do chat do pregão."""
    conn = get_connection()
    horario = body.horario or datetime.now().strftime("%H:%M:%S")
    conn.execute(
        "INSERT INTO chat_pregao (pregao_id, remetente, mensagem, horario) VALUES (?, ?, ?, ?)",
        (pregao_id, body.remetente, body.mensagem, horario))
    conn.commit()
    return {"ok": True}


# ── Eventos/Timeline ──

@router.post("/{pregao_id}/eventos")
def registrar_evento(pregao_id: int, body: EventoCreate):
    """Registra evento/movimentação do pregão."""
    conn = get_connection()
    data_hora = body.data_hora or datetime.now().isoformat()
    conn.execute(
        "INSERT INTO pregao_eventos (pregao_id, tipo, descricao, data_hora) VALUES (?, ?, ?, ?)",
        (pregao_id, body.tipo, body.descricao, data_hora))
    conn.commit()
    return {"ok": True}


# ── Buscar resultado multi-portal ──

@router.post("/{pregao_id}/buscar-resultado")
def buscar_resultado_multiportal_route(pregao_id: int):
    """Busca resultado do pregão em TODOS os portais disponíveis."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from api.portais.manager import buscar_resultado_multiportal

    conn = get_connection()
    pregao = conn.execute("SELECT * FROM pregoes WHERE id = ?", (pregao_id,)).fetchone()
    if not pregao:
        raise HTTPException(404, "Pregão não encontrado")

    pncp_id = pregao["pncp_id"]
    portal_hint = pregao["portal"]

    # Pega UASG do edital
    edital = conn.execute("SELECT uasg, portal FROM editais WHERE pncp_id = ?", (pncp_id,)).fetchone()
    uasg = edital["uasg"] if edital else None

    # Busca em todos os portais
    resultado = buscar_resultado_multiportal(pncp_id, portal_hint=portal_hint or (edital["portal"] if edital else None), uasg=uasg)
    melhor = resultado["melhor"]

    # Se encontrou classificação, salva no banco
    if melhor.get("classificacao"):
        conn.execute("DELETE FROM pregao_classificacao WHERE pregao_id = ?", (pregao_id,))
        for emp in melhor["classificacao"]:
            conn.execute("""
                INSERT INTO pregao_classificacao (pregao_id, posicao, empresa, cnpj, valor_lance_final, habilitado)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pregao_id, emp["posicao"], emp["empresa"], emp.get("cnpj"), emp.get("valor_lance_final"), 1 if emp.get("habilitado") else 0))

        # Atualiza vencedor
        if melhor.get("vencedor_nome"):
            conn.execute("""UPDATE pregoes SET vencedor_nome = ?, vencedor_valor = ?, total_participantes = ?,
                status = 'resultado', updated_at = datetime('now') WHERE id = ?""",
                (melhor["vencedor_nome"], melhor["vencedor_valor"], melhor["total_participantes"], pregao_id))

        # Evento
        conn.execute("INSERT INTO pregao_eventos (pregao_id, tipo, descricao, data_hora) VALUES (?, ?, ?, ?)",
            (pregao_id, "resultado", f"Resultado importado de {melhor['portal']}: {melhor['vencedor_nome']} venceu com {melhor['vencedor_valor']}", datetime.now().isoformat()))
        conn.commit()

    # Salva mensagens se houver
    if melhor.get("mensagens"):
        for msg in melhor["mensagens"]:
            conn.execute("INSERT INTO chat_pregao (pregao_id, remetente, mensagem, horario) VALUES (?, ?, ?, ?)",
                (pregao_id, msg.get("remetente", "sistema"), msg.get("mensagem"), msg.get("horario")))
        conn.commit()

    # Salva lances se houver
    if melhor.get("lances"):
        for lance in melhor["lances"]:
            conn.execute("INSERT INTO lances (pregao_id, empresa, valor, horario, nosso) VALUES (?, ?, ?, ?, ?)",
                (pregao_id, lance.get("empresa"), lance.get("valor"), lance.get("horario"), 1 if lance.get("nosso") else 0))
        conn.commit()

    return {
        "melhor_portal": melhor.get("portal", "nenhum"),
        "status_pregao": melhor.get("status_pregao", ""),
        "classificacao": len(melhor.get("classificacao", [])),
        "vencedor": melhor.get("vencedor_nome", ""),
        "erros": resultado.get("erros", []),
        "portais_consultados": list(resultado.get("portais", {}).keys()),
        "mensagem": f"Consultados: {', '.join(resultado.get('portais', {}).keys())}. " + (
            f"Vencedor: {melhor['vencedor_nome']}" if melhor.get("vencedor_nome")
            else "Resultado ainda não publicado. " + "; ".join(resultado.get("erros", []))
        ),
    }


@router.get("/portais/status")
def listar_portais():
    """Lista todos os portais e seu status de integração."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from api.portais.manager import listar_portais_status
    return listar_portais_status()


# ── Sync da extensão Chrome ──

@router.post("/extension/sync")
async def extension_sync(request: Request):
    """Recebe dados capturados pela extensão Chrome de qualquer portal."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "JSON inválido"}
    conn = get_connection()

    portal = body.get("portal", "desconhecido")
    compra_id = body.get("compra_id", "")
    classificacao = body.get("classificacao", [])
    lances = body.get("lances", [])
    mensagens = body.get("mensagens", [])
    propostas = body.get("propostas", [])

    saved = {"classificacao": 0, "lances": 0, "mensagens": 0}

    # Extrai info da URL/página
    page_url = body.get("url", "")
    page_title = body.get("title", "")
    uasg = ""
    numero_pregao = ""
    orgao_nome = ""
    objeto = ""

    # Extrai UASG e número do compra_id (formato: UASG+MODALIDADE+NUMERO)
    if compra_id and len(compra_id) > 10:
        uasg = compra_id[:6]

    # Extrai do título/texto da página
    titulo_texto = body.get("titulo", "") or page_title
    import re

    uasg_match = re.search(r'UASG\s*(\d{5,6})', titulo_texto)
    if uasg_match:
        uasg = uasg_match.group(1)
    pregao_match = re.search(r'N[°º]?\s*(\d+/\d{4})', titulo_texto)
    if pregao_match:
        numero_pregao = pregao_match.group(1)

    # Extrai nome do órgão — prioridade: campo direto > regex UASG > titulo
    orgao_ext = body.get("orgao_nome", "")
    # Limpa se veio com número de lei ou UASG
    if orgao_ext and not re.match(r'^N[°º]|^UASG|^\d|^Lei|^\(', orgao_ext):
        orgao_nome = orgao_ext
    else:
        # Tenta extrair do texto UASG XXX - NOME DO ORGAO
        orgao_match = re.search(r'UASG\s*\d+\s*-\s*([A-ZÀ-Ú][A-ZÀ-Ú\s\.\-/]+?)(?:\s*Critério|\s*Modo|\s*$)', titulo_texto)
        if orgao_match:
            orgao_nome = orgao_match.group(1).strip()
        # Fallback: busca "PREFEITURA|UNIVERSIDADE|TRIBUNAL|SECRETARIA..." no texto
        if not orgao_nome:
            nome_match = re.search(r'(PREFEITURA|UNIVERSIDADE|TRIBUNAL|SECRETARIA|INSTITUTO|MINISTÉRIO|FUNDAÇÃO|EMPRESA|COMPANHIA|AGÊNCIA)[A-ZÀ-Ú\s\.\-/]{5,60}', titulo_texto)
            if nome_match:
                orgao_nome = nome_match.group(0).strip()

    # Limpa prefixos comuns (MRJ-, MEC-, MIN-, GOV-, etc.)
    if orgao_nome:
        orgao_nome = re.sub(r'^[A-Z]{2,5}-\s*', '', orgao_nome).strip()
        # Remove sufixos ruins
        orgao_nome = re.sub(r'\s*Critério.*$', '', orgao_nome).strip()
        orgao_nome = re.sub(r'\s*Modo.*$', '', orgao_nome).strip()

    # Tenta achar pregão existente
    pregao = None
    if compra_id:
        pregao = conn.execute("SELECT id FROM pregoes WHERE link_portal LIKE ? OR observacoes LIKE ? LIMIT 1",
                              (f"%{compra_id}%", f"%{compra_id}%")).fetchone()

    if not pregao and uasg:
        # Busca por UASG no edital
        edital = conn.execute("SELECT pncp_id FROM editais WHERE uasg = ? LIMIT 1", (uasg,)).fetchone()
        if edital:
            pregao = conn.execute("SELECT id FROM pregoes WHERE pncp_id = ?", (edital["pncp_id"],)).fetchone()

    # Se não existe edital nem pregão, cria ambos automaticamente
    if not pregao:
        # Cria edital fake com dados da extensão
        fake_pncp_id = f"EXT-{compra_id or uasg or 'unknown'}"
        existing_ed = conn.execute("SELECT pncp_id FROM editais WHERE pncp_id = ?", (fake_pncp_id,)).fetchone()
        if not existing_ed:
            valor_teto = 0
            if classificacao:
                # Estima valor pelo maior lance
                vals = [c.get("valor_lance_final", 0) or 0 for c in classificacao]
                valor_teto = max(vals) if vals else 0

            # Extrai objeto do título da página
            titulo_raw = body.get("titulo", "") or body.get("title", "")
            objeto = ""
            # Tenta pegar texto após o número do pregão (ex: "Obras Civis Públicas")
            import re as _re
            obj_match = _re.search(r'(?:Pregão|Concorrência|Dispensa)[^0-9]*\d+/\d{4}[^)]*\)\s*(.*?)(?:Critério|Modo|$)', titulo_raw, _re.DOTALL)
            if obj_match:
                objeto = obj_match.group(1).strip()[:200]
            # Fallback: pega o texto principal entre UASG e Critério
            if not objeto:
                obj_match2 = _re.search(r'UASG\s*\d+\s*-\s*[^\n]+\n+(.*?)(?:Critério|Modo|\d+\s+Contratação)', titulo_raw, _re.DOTALL)
                if obj_match2:
                    objeto = obj_match2.group(1).strip()[:200]
            if not objeto:
                objeto = f"{numero_pregao or 'Pregão'} - {orgao_nome or 'UASG ' + uasg}"

            conn.execute("""INSERT INTO editais (pncp_id, orgao_nome, objeto, valor_estimado, uf, status, score_relevancia, uasg, portal, fonte)
                VALUES (?, ?, ?, ?, 'RJ', 'pregao_ext', 0, ?, ?, 'extension')""",
                (fake_pncp_id, orgao_nome or f"UASG {uasg}", objeto, valor_teto, uasg, portal))

        # Tenta buscar dados complementares no PNCP
        try:
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from agente1_monitor.pncp_client import buscar_editais_por_texto
            if orgao_nome and numero_pregao:
                search_q = f"{orgao_nome} {numero_pregao}"
            elif orgao_nome:
                search_q = orgao_nome
            else:
                search_q = None

            if search_q:
                pncp_results = buscar_editais_por_texto(search_q, tam_pagina=5, paginas=1, uf=body.get("uf"))
                if pncp_results:
                    best = pncp_results[0]
                    pncp_valor = best.get("valor_global") or 0
                    pncp_orgao = best.get("orgao_nome") or ""
                    pncp_objeto = best.get("description") or ""
                    pncp_id_real = best.get("pncp_id") or ""
                    # Atualiza edital com dados do PNCP
                    updates = []
                    vals = []
                    if pncp_valor and pncp_valor > valor_teto:
                        updates.append("valor_estimado = ?"); vals.append(pncp_valor)
                    if pncp_orgao and len(pncp_orgao) > len(orgao_nome or ""):
                        updates.append("orgao_nome = ?"); vals.append(pncp_orgao)
                    if pncp_objeto and len(pncp_objeto) > len(objeto or ""):
                        updates.append("objeto = ?"); vals.append(pncp_objeto)
                    if updates:
                        vals.append(fake_pncp_id)
                        conn.execute(f"UPDATE editais SET {', '.join(updates)} WHERE pncp_id = ?", vals)
                        conn.commit()
        except Exception as _e:
            pass  # Não bloqueia se PNCP falhar

        # Cria pregão
        existing_pg = conn.execute("SELECT id FROM pregoes WHERE pncp_id = ?", (fake_pncp_id,)).fetchone()
        if not existing_pg:
            conn.execute("""INSERT INTO pregoes (pncp_id, status, portal, link_portal, observacoes)
                VALUES (?, 'em_disputa', ?, ?, ?)""",
                (fake_pncp_id, portal, page_url, f"compra_id={compra_id} UASG={uasg} {numero_pregao}"))
            conn.commit()

        pregao = conn.execute("SELECT id FROM pregoes WHERE pncp_id = ?", (fake_pncp_id,)).fetchone()

    pregao_id = pregao["id"]

    # Salva classificação
    if classificacao:
        for emp in classificacao:
            existing = conn.execute("SELECT id FROM pregao_classificacao WHERE pregao_id = ? AND cnpj = ?",
                                    (pregao_id, emp.get("cnpj"))).fetchone()
            if not existing:
                conn.execute("""INSERT INTO pregao_classificacao (pregao_id, posicao, empresa, cnpj, valor_lance_final, habilitado)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (pregao_id, emp.get("posicao", 0), emp.get("empresa", ""), emp.get("cnpj"),
                     emp.get("valor_lance_final"), 1 if emp.get("habilitado", True) else 0))
                saved["classificacao"] += 1

    # Salva lances
    if lances:
        for lance in lances:
            conn.execute("INSERT INTO lances (pregao_id, empresa, valor, horario, nosso) VALUES (?, ?, ?, ?, 0)",
                (pregao_id, lance.get("empresa", ""), lance.get("valor"), lance.get("horario")))
            saved["lances"] += 1

    # Salva mensagens
    if mensagens:
        for msg in mensagens:
            conn.execute("INSERT INTO chat_pregao (pregao_id, remetente, mensagem, horario) VALUES (?, ?, ?, ?)",
                (pregao_id, msg.get("remetente", "sistema"), msg.get("mensagem", ""), msg.get("horario")))
            saved["mensagens"] += 1

    # Atualiza vencedor = primeira empresa HABILITADA
    if classificacao and len(classificacao) > 0:
        sorted_class = sorted(classificacao, key=lambda x: x.get("posicao", 999))
        vencedor = None
        for emp in sorted_class:
            if emp.get("habilitado", True):
                vencedor = emp
                break
        if not vencedor:
            vencedor = sorted_class[0]

        # Atualiza pregão com vencedor e nossa posição
        nossa_posicao = body.get("nossa_posicao")
        nosso_lance = body.get("nosso_lance")
        orgao_nome = body.get("orgao_nome", "")

        conn.execute("""UPDATE pregoes SET vencedor_nome = ?, vencedor_valor = ?, total_participantes = ?,
            posicao_final = ?, lance_final = ?, nossa_empresa = ?,
            status = 'resultado', updated_at = datetime('now') WHERE id = ?""",
            (vencedor.get("empresa"), vencedor.get("valor_lance_final"), len(classificacao),
             nossa_posicao, nosso_lance, body.get("nossa_empresa", "MANUTEC"), pregao_id))

        # Atualiza edital com orgão se veio
        if orgao_nome:
            conn.execute("UPDATE editais SET orgao_nome = ? WHERE pncp_id = (SELECT pncp_id FROM pregoes WHERE id = ?)",
                         (orgao_nome, pregao_id))

    conn.commit()

    return {
        "ok": True,
        "pregao_id": pregao_id,
        "portal": portal,
        "saved": saved,
        "message": f"Portal {portal}: {saved['classificacao']} empresas, {saved['lances']} lances, {saved['mensagens']} mensagens salvos.",
    }


# ── Classificação ──

class ClassificacaoCreate(BaseModel):
    posicao: int
    empresa: str
    cnpj: Optional[str] = None
    valor_proposta: Optional[float] = None
    valor_lance_final: Optional[float] = None
    desconto_pct: Optional[float] = None
    habilitado: bool = True
    observacao: Optional[str] = None


@router.get("/{pregao_id}/classificacao")
def listar_classificacao(pregao_id: int):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM pregao_classificacao WHERE pregao_id = ? ORDER BY posicao", (pregao_id,)).fetchall()
    return [dict(r) for r in rows]


@router.post("/{pregao_id}/classificacao")
def adicionar_classificacao(pregao_id: int, body: ClassificacaoCreate):
    conn = get_connection()
    conn.execute("""
        INSERT INTO pregao_classificacao (pregao_id, posicao, empresa, cnpj, valor_proposta, valor_lance_final, desconto_pct, habilitado, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pregao_id, body.posicao, body.empresa, body.cnpj, body.valor_proposta, body.valor_lance_final, body.desconto_pct, 1 if body.habilitado else 0, body.observacao))
    conn.commit()
    return {"ok": True}


class HabilitacaoUpdate(BaseModel):
    habilitado: bool


@router.put("/{pregao_id}/classificacao/{class_id}/habilitacao")
def atualizar_habilitacao(pregao_id: int, class_id: int, body: HabilitacaoUpdate):
    """Atualiza status de habilitação de uma empresa na classificação."""
    conn = get_connection()
    conn.execute("UPDATE pregao_classificacao SET habilitado = ? WHERE id = ? AND pregao_id = ?",
                 (1 if body.habilitado else 0, class_id, pregao_id))
    conn.commit()
    return {"ok": True}


@router.delete("/{pregao_id}/classificacao/{class_id}")
def remover_classificacao(pregao_id: int, class_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM pregao_classificacao WHERE id = ? AND pregao_id = ?", (class_id, pregao_id))
    conn.commit()
    return {"ok": True}


# ── Sync da Chrome Extension ──

class ComprasGovSyncData(BaseModel):
    tipo: str
    url: str
    timestamp: str
    compra_id: Optional[str] = None
    status: Optional[str] = None
    lances: list = []
    mensagens: list = []
    classificacao: list = []
    propostas: list = []


@router.post("/comprasgov/sync")
def sync_comprasgov(body: ComprasGovSyncData):
    """Recebe dados do ComprasGov via Chrome Extension."""
    conn = get_connection()

    # Tenta encontrar pregão pelo compra_id (formato UASG-MOD-NUM)
    compra_id = body.compra_id or ""
    parts = compra_id.split("-")
    uasg = parts[0] if len(parts) >= 1 else ""

    # Busca pregão que tenha essa UASG
    pregao = None
    if uasg:
        pregao = conn.execute("""
            SELECT p.id, p.pncp_id FROM pregoes p
            JOIN editais e ON p.pncp_id = e.pncp_id
            WHERE e.uasg = ?
            ORDER BY p.created_at DESC LIMIT 1
        """, (uasg,)).fetchone()

    if not pregao:
        # Tenta por qualquer pregão ativo
        pregao = conn.execute("SELECT id, pncp_id FROM pregoes ORDER BY created_at DESC LIMIT 1").fetchone()

    synced = {"lances": 0, "mensagens": 0, "classificacao": 0}

    if pregao:
        pregao_id = pregao["id"]

        # Salva classificação
        if body.classificacao:
            conn.execute("DELETE FROM pregao_classificacao WHERE pregao_id = ?", (pregao_id,))
            for c in body.classificacao:
                conn.execute("""
                    INSERT INTO pregao_classificacao (pregao_id, posicao, empresa, cnpj, valor_lance_final, habilitado)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (pregao_id, c.get("posicao", 0), c.get("empresa", ""), c.get("cnpj"),
                      c.get("valor_lance_final"), 1 if c.get("habilitado", True) else 0))
            synced["classificacao"] = len(body.classificacao)

            # Atualiza vencedor
            if body.classificacao:
                venc = body.classificacao[0]
                conn.execute("""UPDATE pregoes SET vencedor_nome = ?, vencedor_valor = ?,
                    total_participantes = ?, updated_at = datetime('now') WHERE id = ?""",
                    (venc.get("empresa"), venc.get("valor_lance_final"), len(body.classificacao), pregao_id))

        # Salva lances
        if body.lances:
            for l in body.lances:
                existing = conn.execute(
                    "SELECT id FROM lances WHERE pregao_id = ? AND empresa = ? AND valor = ?",
                    (pregao_id, l.get("empresa", ""), l.get("valor"))
                ).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO lances (pregao_id, empresa, valor, horario, nosso) VALUES (?, ?, ?, ?, 0)",
                        (pregao_id, l.get("empresa", ""), l.get("valor"), l.get("horario")))
                    synced["lances"] += 1

        # Salva mensagens
        if body.mensagens:
            for m in body.mensagens:
                msg_text = m.get("mensagem", "")[:500]
                existing = conn.execute(
                    "SELECT id FROM chat_pregao WHERE pregao_id = ? AND mensagem = ?",
                    (pregao_id, msg_text)
                ).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO chat_pregao (pregao_id, remetente, mensagem, horario) VALUES (?, ?, ?, ?)",
                        (pregao_id, m.get("remetente", "sistema"), msg_text, m.get("horario")))
                    synced["mensagens"] += 1

        # Evento
        if any(v > 0 for v in synced.values()):
            conn.execute("INSERT INTO pregao_eventos (pregao_id, tipo, descricao, data_hora) VALUES (?, ?, ?, ?)",
                (pregao_id, "sync", f"Chrome Extension: {synced['classificacao']} class, {synced['lances']} lances, {synced['mensagens']} msgs",
                 datetime.now().isoformat()))

        conn.commit()

    return {
        "ok": True,
        "pregao_id": pregao["id"] if pregao else None,
        "synced": synced,
    }


# ── Por edital ──

@router.get("/edital/{pncp_id:path}")
def pregao_por_edital(pncp_id: str):
    """Busca pregão pelo pncp_id do edital."""
    conn = get_connection()
    pregao = conn.execute("SELECT * FROM pregoes WHERE pncp_id = ?", (pncp_id,)).fetchone()
    if not pregao:
        return {"pregao": None}

    pregao_id = pregao["id"]
    lances = conn.execute("SELECT * FROM lances WHERE pregao_id = ? ORDER BY id", (pregao_id,)).fetchall()
    chat = conn.execute("SELECT * FROM chat_pregao WHERE pregao_id = ? ORDER BY id", (pregao_id,)).fetchall()
    eventos = conn.execute("SELECT * FROM pregao_eventos WHERE pregao_id = ? ORDER BY id DESC", (pregao_id,)).fetchall()
    classificacao = conn.execute("SELECT * FROM pregao_classificacao WHERE pregao_id = ? ORDER BY posicao", (pregao_id,)).fetchall()

    return {
        "pregao": dict(pregao),
        "lances": [dict(l) for l in lances],
        "chat": [dict(c) for c in chat],
        "eventos": [dict(e) for e in eventos],
        "classificacao": [dict(c) for c in classificacao],
    }
