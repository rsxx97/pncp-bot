"""Detecta eventos comparando snapshot anterior x atual."""
from __future__ import annotations

from typing import Iterable

from radar.adapters.base import PregaoSnapshot
from radar.eventos.tipos import EventoRadar, TipoEvento


def detectar_eventos(
    *,
    tenant_id: int,
    pregao_monitorado_id: int,
    anterior: PregaoSnapshot | None,
    atual: PregaoSnapshot,
    cnpj_proprio: str | None = None,
) -> list[EventoRadar]:
    """Compara `anterior` (do DB) com `atual` (acabou de ser fetched). Retorna eventos.

    Se `anterior` é None (1ª vez), só emite eventos de "estado atual"
    (ex: SESSAO_ABERTA se já está em sessão).
    """
    eventos: list[EventoRadar] = []

    base_kwargs = dict(tenant_id=tenant_id, pregao_monitorado_id=pregao_monitorado_id)

    if anterior is None:
        if atual.status == "em_sessao":
            eventos.append(EventoRadar.criar(
                TipoEvento.SESSAO_ABERTA, titulo="Sessão em andamento",
                descricao=f"{atual.orgao or ''} — {atual.objeto or ''}"[:200],
                payload={"snapshot": atual.to_dict()},
                **base_kwargs,
            ))
        return eventos

    # Status
    if anterior.status != atual.status:
        eventos.extend(_eventos_status(anterior, atual, base_kwargs))

    # Fase
    if anterior.fase != atual.fase and atual.fase:
        eventos.append(EventoRadar.criar(
            TipoEvento.MUDANCA_FASE,
            titulo=f"Fase: {anterior.fase or '-'} → {atual.fase}",
            descricao=atual.objeto or "",
            payload={"fase_anterior": anterior.fase, "fase_atual": atual.fase},
            **base_kwargs,
        ))

    # Lances
    eventos.extend(_eventos_lances(anterior, atual, base_kwargs, cnpj_proprio))

    # Posição
    if anterior.minha_posicao and atual.minha_posicao:
        if anterior.minha_posicao == 1 and atual.minha_posicao > 1:
            eventos.append(EventoRadar.criar(
                TipoEvento.USUARIO_SUPERADO,
                titulo=f"Você foi superado — posição {atual.minha_posicao}º",
                descricao=f"Melhor lance: R$ {atual.melhor_lance or 0:,.2f}",
                payload={"posicao_anterior": 1, "posicao_atual": atual.minha_posicao},
                **base_kwargs,
            ))
        elif anterior.minha_posicao > 1 and atual.minha_posicao == 1:
            eventos.append(EventoRadar.criar(
                TipoEvento.USUARIO_NA_FRENTE,
                titulo="Você voltou pra 1ª colocação",
                descricao=f"Seu lance: R$ {atual.meu_melhor_lance or 0:,.2f}",
                payload={"posicao_anterior": anterior.minha_posicao, "posicao_atual": 1},
                **base_kwargs,
            ))

    # Mensagens novas do pregoeiro
    novas_msgs = _mensagens_novas(anterior.mensagens, atual.mensagens)
    for msg in novas_msgs:
        eventos.append(EventoRadar.criar(
            TipoEvento.MENSAGEM_PREGOEIRO,
            titulo="Mensagem do pregoeiro",
            descricao=(msg.get("texto") or "")[:200],
            payload={"mensagem": msg},
            **base_kwargs,
        ))

    return eventos


def _eventos_status(prev: PregaoSnapshot, curr: PregaoSnapshot, base_kwargs: dict) -> list[EventoRadar]:
    transicao = (prev.status, curr.status)
    mapa = {
        ("agendado", "em_sessao"):       (TipoEvento.SESSAO_ABERTA, "Sessão aberta"),
        ("em_sessao", "suspenso"):       (TipoEvento.SESSAO_SUSPENSA, "Sessão suspensa"),
        ("suspenso", "em_sessao"):       (TipoEvento.SESSAO_RETOMADA, "Sessão retomada"),
        ("em_sessao", "encerrado"):      (TipoEvento.SESSAO_ENCERRADA, "Sessão encerrada"),
        ("em_sessao", "fracassado"):     (TipoEvento.FRACASSADO, "Pregão fracassado"),
        ("em_sessao", "deserto"):        (TipoEvento.DESERTO, "Pregão deserto"),
        ("agendado", "encerrado"):       (TipoEvento.CANCELAMENTO, "Pregão cancelado"),
    }
    if transicao in mapa:
        tipo, titulo = mapa[transicao]
        return [EventoRadar.criar(
            tipo, titulo=titulo, descricao=curr.objeto or "",
            payload={"status_anterior": prev.status, "status_atual": curr.status},
            **base_kwargs,
        )]
    return []


def _eventos_lances(prev: PregaoSnapshot, curr: PregaoSnapshot, base_kwargs: dict, cnpj_proprio: str | None) -> list[EventoRadar]:
    eventos = []
    prev_ids = {l.get("id") or f"{l.get('cnpj')}-{l.get('valor')}-{l.get('horario')}" for l in prev.lances}
    for lance in curr.lances:
        lid = lance.get("id") or f"{lance.get('cnpj')}-{lance.get('valor')}-{lance.get('horario')}"
        if lid in prev_ids:
            continue
        proprio = bool(cnpj_proprio and lance.get("cnpj") == cnpj_proprio)
        eventos.append(EventoRadar.criar(
            TipoEvento.NOVO_LANCE,
            titulo=("Seu lance registrado" if proprio else "Novo lance de concorrente"),
            descricao=f"R$ {lance.get('valor', 0):,.2f}",
            payload={"lance": lance, "proprio": proprio},
            **base_kwargs,
        ))
    return eventos


def _chave_msg(m: dict) -> str:
    """Chave estável pra dedup msgs. Prefere chaveMensagemNaOrigem (UUID SERPRO)."""
    raw = m.get("raw") or {}
    return (
        raw.get("chaveMensagemNaOrigem")
        or m.get("id")
        or f"{m.get('horario')}|{(m.get('texto') or '')[:50]}"
    )


def _mensagens_novas(prev: list[dict], curr: list[dict]) -> list[dict]:
    prev_ids = {_chave_msg(m) for m in prev}
    return [m for m in curr if _chave_msg(m) not in prev_ids]
