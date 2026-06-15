"""Worker do Radar: para cada pregão due, busca snapshot, detecta eventos, dispara."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta

from radar.adapters.base import (
    AuthError,
    CaptchaError,
    NotFoundError,
    PregaoSnapshot,
    RateLimitError,
)
from radar.adapters.registry import get_adapter
from radar.credenciais import decifrar, decifrar_dict
from radar.eventos.detector import detectar_eventos
from radar.eventos.dispatcher import dispatcher
from radar.metrics import RADAR_FETCH_DURACAO, RADAR_FETCH_TOTAL, RADAR_PREGOES_ATIVOS

log = logging.getLogger("radar.monitor")

# Cache compartilhado: 1 fetch atende N clientes do mesmo pregão
# Aumentado pra economizar captcha — pra 60s no em_sessao, 15min no agendado
CACHE_TTL_EM_SESSAO_SEG = int(os.environ.get("RADAR_CACHE_EM_SESSAO_SEG", "60"))   # em_sessao: cache vence em 60s
CACHE_TTL_AGENDADO_SEG = int(os.environ.get("RADAR_CACHE_AGENDADO_SEG", "900"))    # agendado: cache vence em 15min
CACHE_TTL_ENCERRADO_SEG = int(os.environ.get("RADAR_CACHE_ENCERRADO_SEG", "86400"))  # encerrado: 1 dia

# Polling adaptativo por status — quando agendar próxima consulta
# Endpoint público SERPRO só retorna ~20 msgs mais recentes; precisamos checar
# rápido pra capturar msgs novas antes de saírem do limite (e ficarem perdidas).
INTERVALO_EM_SESSAO_SEG = 30        # 30s em sessão — captura msgs antes do truncamento
INTERVALO_AGENDADO_SEG = 1800       # 30min em pregão agendado (sem disputa)
INTERVALO_ENCERRADO_SEG = 86400     # encerrado: 1 dia
INTERVALO_PROXIMO_ABERTURA_SEG = 60  # 1min quando faltar < 1h pra abertura


def _intervalo_proximo_poll(status: str, snap_dict: dict | None = None) -> int:
    """Polling adaptativo — Elicita-style. Reduz fetches em pregões inativos."""
    if status == "em_sessao":
        return INTERVALO_EM_SESSAO_SEG
    if status in ("encerrado", "fracassado", "deserto", "homologado", "adjudicado"):
        return INTERVALO_ENCERRADO_SEG
    # agendado/suspenso — vê se tá próximo de abrir
    if snap_dict:
        abertura = snap_dict.get("data_abertura")
        if abertura:
            try:
                t_abertura = datetime.fromisoformat(abertura.replace("Z", ""))
                seg_pra_abertura = (t_abertura - datetime.now()).total_seconds()
                if 0 < seg_pra_abertura < 3600:  # < 1h
                    return INTERVALO_PROXIMO_ABERTURA_SEG
            except (ValueError, TypeError):
                pass
    return INTERVALO_AGENDADO_SEG


def _ler_cache(portal_slug: str, identificador: str, ttl_seg: int) -> dict | None:
    """Tenta ler snapshot recente do cache compartilhado."""
    from shared.database import get_db
    try:
        r = get_db().execute(
            "SELECT snapshot_json, atualizado_em FROM radar_snapshot_cache "
            "WHERE portal_slug = ? AND identificador = ?",
            (portal_slug, identificador),
        ).fetchone()
        if not r:
            return None
        atualizado_em = datetime.fromisoformat(r["atualizado_em"])
        idade = (datetime.now() - atualizado_em).total_seconds()
        if idade > ttl_seg:
            return None
        return json.loads(r["snapshot_json"])
    except Exception as e:
        log.warning(f"falha lendo cache {portal_slug}/{identificador}: {e}")
        return None


def _gravar_cache(portal_slug: str, identificador: str, snap_dict: dict) -> None:
    """Grava snapshot no cache compartilhado."""
    from shared.database import get_db
    try:
        get_db().execute(
            """INSERT INTO radar_snapshot_cache (portal_slug, identificador, snapshot_json, atualizado_em)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(portal_slug, identificador) DO UPDATE SET
                 snapshot_json = excluded.snapshot_json,
                 atualizado_em = datetime('now')""",
            (portal_slug, identificador, json.dumps(snap_dict, ensure_ascii=False, default=str)),
        )
        get_db().commit()
    except Exception as e:
        log.warning(f"falha gravando cache {portal_slug}/{identificador}: {e}")


async def tick_uma_vez() -> dict:
    """Roda 1 ciclo: pega pregões com proxima_consulta_em <= agora, processa em paralelo (limite 10)."""
    from shared.database import get_db

    conn = get_db()
    agora = datetime.now().isoformat()
    rows = conn.execute(
        """SELECT p.*, po.slug AS portal_slug
           FROM radar_pregoes_monitorados p
           JOIN portais po ON po.id = p.portal_id
           WHERE p.silenciado = 0
             AND (p.proxima_consulta_em IS NULL OR p.proxima_consulta_em <= ?)
             AND po.ativo = 1
           ORDER BY p.proxima_consulta_em ASC
           LIMIT 50""",
        (agora,),
    ).fetchall()

    if not rows:
        return {"processados": 0, "erros": 0}

    sem = asyncio.Semaphore(10)

    async def _go(row):
        async with sem:
            return await _processar(dict(row))

    resultados = await asyncio.gather(*[_go(r) for r in rows], return_exceptions=True)
    ok = sum(1 for r in resultados if r is True)
    erros = sum(1 for r in resultados if r is not True)
    log.info(f"Radar tick: {ok} OK, {erros} erros, {len(rows)} processados")
    return {"processados": len(rows), "ok": ok, "erros": erros}


async def _processar(pregao_row: dict) -> bool:
    slug = pregao_row["portal_slug"]
    pid = pregao_row["id"]
    tenant_id = pregao_row["tenant_id"]
    identificador = pregao_row["identificador"]

    creds = _carregar_credenciais(tenant_id, pregao_row["portal_id"])
    adapter = get_adapter(slug, credenciais=creds)

    t0 = time.monotonic()
    # CACHE COMPARTILHADO: tenta reusar snapshot fresco de outros clientes monitorando este mesmo pregão
    status_atual = pregao_row.get("status", "agendado")
    if status_atual == "em_sessao":
        cache_ttl = CACHE_TTL_EM_SESSAO_SEG
    elif status_atual in ("encerrado", "fracassado", "deserto", "homologado", "adjudicado"):
        cache_ttl = CACHE_TTL_ENCERRADO_SEG
    else:
        cache_ttl = CACHE_TTL_AGENDADO_SEG

    snap_cached = _ler_cache(slug, identificador, cache_ttl)
    if snap_cached:
        log.info(f"[cache HIT] {slug}/{identificador} (ttl={cache_ttl}s) — evitou fetch real")
        from radar.adapters.base import PregaoSnapshot
        try:
            snap = PregaoSnapshot(
                portal_slug=snap_cached.get("portal_slug", slug),
                identificador=snap_cached.get("identificador", identificador),
                numero=snap_cached.get("numero"),
                orgao=snap_cached.get("orgao"),
                objeto=snap_cached.get("objeto"),
                status=snap_cached.get("status", "agendado"),
                fase=snap_cached.get("fase"),
                valor_estimado=snap_cached.get("valor_estimado"),
                melhor_lance=snap_cached.get("melhor_lance"),
                melhor_lance_cnpj=snap_cached.get("melhor_lance_cnpj"),
                minha_posicao=snap_cached.get("minha_posicao"),
                meu_melhor_lance=snap_cached.get("meu_melhor_lance"),
                mensagens=snap_cached.get("mensagens") or [],
                lances=snap_cached.get("lances") or [],
            )
            RADAR_FETCH_TOTAL.labels(portal=slug, status="cache_hit").inc()
            # Pula pro fluxo de detect+save com snapshot do cache
            anterior = _snapshot_anterior(pregao_row.get("snapshot_json"))
            cnpj_proprio = (creds or {}).get("cnpj") if creds else None
            eventos = detectar_eventos(
                tenant_id=tenant_id, pregao_monitorado_id=pid,
                anterior=anterior, atual=snap, cnpj_proprio=cnpj_proprio,
            )
            for ev in eventos:
                await dispatcher.emit(ev, portal_slug=slug)
                try:
                    from radar.notificacoes.registry import disparar_evento
                    await disparar_evento(ev)
                except Exception as e:
                    log.exception(f"falha dispatch {ev.tipo.value}: {e}")
            _salvar_snapshot(pid, snap)
            _agendar_proximo(pid, pregao_row, base_seg=_intervalo_proximo_poll(snap.status, snap_cached))
            return True
        except Exception as e:
            log.warning(f"cache HIT mas falha ao parsear: {e}; refazendo fetch real")

    # CACHE MISS: faz fetch real
    try:
        if adapter.requer_credencial and creds:
            await adapter.autenticar()
        snap = await adapter.fetch_pregao(identificador)
        RADAR_FETCH_TOTAL.labels(portal=slug, status="ok").inc()
        # Grava no cache compartilhado pra próximos clientes
        try: _gravar_cache(slug, identificador, snap.to_dict())
        except Exception: pass
    except NotFoundError as e:
        RADAR_FETCH_TOTAL.labels(portal=slug, status="not_found").inc()
        _agendar_proximo(pid, pregao_row, base_seg=3600)
        log.warning(f"Pregão {identificador} não encontrado: {e}")
        return False
    except RateLimitError as e:
        RADAR_FETCH_TOTAL.labels(portal=slug, status="rate_limit").inc()
        _agendar_proximo(pid, pregao_row, base_seg=max(60, int(e.retry_em)))
        log.warning(f"Rate limit {slug}: aguardando {e.retry_em}s")
        return False
    except (AuthError, CaptchaError) as e:
        RADAR_FETCH_TOTAL.labels(portal=slug, status="auth_error").inc()
        _marcar_credencial_erro(tenant_id, pregao_row["portal_id"], str(e))
        _agendar_proximo(pid, pregao_row, base_seg=1800)
        return False
    except NotImplementedError as e:
        RADAR_FETCH_TOTAL.labels(portal=slug, status="not_implemented").inc()
        _agendar_proximo(pid, pregao_row, base_seg=3600)
        return False
    except Exception as e:
        RADAR_FETCH_TOTAL.labels(portal=slug, status="erro").inc()
        log.exception(f"Erro fetch {slug}/{identificador}: {e}")
        _agendar_proximo(pid, pregao_row, base_seg=300)
        return False
    finally:
        RADAR_FETCH_DURACAO.labels(portal=slug).observe(time.monotonic() - t0)

    anterior = _snapshot_anterior(pregao_row.get("snapshot_json"))
    cnpj_proprio = (creds or {}).get("cnpj") if creds else None
    eventos = detectar_eventos(
        tenant_id=tenant_id,
        pregao_monitorado_id=pid,
        anterior=anterior,
        atual=snap,
        cnpj_proprio=cnpj_proprio,
    )

    for ev in eventos:
        await dispatcher.emit(ev, portal_slug=slug)
        try:
            from radar.notificacoes.registry import disparar_evento
            await disparar_evento(ev)
        except Exception as e:
            log.exception(f"falha ao disparar notificações de {ev.tipo.value}: {e}")

    # Preserva msgs/lances anteriores se o fetch atual veio vazio (SERPRO 204 transiente).
    # Faz UNIÃO por chave única — nunca "perde" msgs/lances já capturados.
    if anterior:
        snap.mensagens = _merge_mensagens(anterior.mensagens or [], snap.mensagens or [])
        snap.lances = _merge_lances(anterior.lances or [], snap.lances or [])

    _salvar_snapshot(pid, snap)
    _agendar_proximo(pid, pregao_row, base_seg=_intervalo_proximo_poll(snap.status, snap.to_dict()))
    return True


def _carregar_credenciais(tenant_id: int, portal_id: int) -> dict | None:
    from shared.database import get_db
    row = get_db().execute(
        "SELECT login_cifrado, senha_cifrada, extra_cifrado FROM credenciais_portal WHERE tenant_id = ? AND portal_id = ?",
        (tenant_id, portal_id),
    ).fetchone()
    if not row:
        return None
    return {
        "_tenant_id": tenant_id,
        "login": decifrar(row["login_cifrado"]),
        "senha": decifrar(row["senha_cifrada"]),
        **((decifrar_dict(row["extra_cifrado"])) or {}),
    }


def _merge_mensagens(anteriores: list[dict], novas: list[dict]) -> list[dict]:
    """Une listas de msgs deduplicando por chave única (id) — preserva tudo já visto."""
    vistos = set()
    out = []
    for m in (anteriores or []) + (novas or []):
        chave = m.get("id") or (m.get("raw") or {}).get("chaveMensagemNaOrigem") or f"{m.get('horario')}-{(m.get('texto') or '')[:50]}"
        if chave in vistos:
            continue
        vistos.add(chave)
        out.append(m)
    # Ordena por horário decrescente (mais recente primeiro)
    out.sort(key=lambda m: m.get("horario") or "", reverse=True)
    return out


def _merge_lances(anteriores: list[dict], novas: list[dict]) -> list[dict]:
    """Pra lances: se atual veio com dados, usa atual (estado mais recente). Senão preserva."""
    return novas if novas else (anteriores or [])


def _snapshot_anterior(snapshot_json: str | None) -> PregaoSnapshot | None:
    if not snapshot_json:
        return None
    try:
        d = json.loads(snapshot_json)
    except json.JSONDecodeError:
        return None
    return PregaoSnapshot(
        portal_slug=d.get("portal_slug", "?"),
        identificador=d.get("identificador", ""),
        numero=d.get("numero"),
        orgao=d.get("orgao"),
        objeto=d.get("objeto"),
        status=d.get("status", "agendado"),
        fase=d.get("fase"),
        valor_estimado=d.get("valor_estimado"),
        melhor_lance=d.get("melhor_lance"),
        melhor_lance_cnpj=d.get("melhor_lance_cnpj"),
        minha_posicao=d.get("minha_posicao"),
        meu_melhor_lance=d.get("meu_melhor_lance"),
        mensagens=d.get("mensagens") or [],
        lances=d.get("lances") or [],
    )


def _salvar_snapshot(pid: int, snap: PregaoSnapshot):
    from shared.database import get_db
    conn = get_db()
    conn.execute(
        """UPDATE radar_pregoes_monitorados
           SET snapshot_json = ?, status = ?, fase = ?, orgao = COALESCE(orgao, ?), objeto = COALESCE(objeto, ?),
               ultima_consulta_em = datetime('now')
           WHERE id = ?""",
        (
            json.dumps(snap.to_dict(), ensure_ascii=False),
            snap.status,
            snap.fase,
            snap.orgao,
            snap.objeto,
            pid,
        ),
    )
    conn.commit()


def _agendar_proximo(pid: int, pregao_row: dict, base_seg: int | None = None, em_sessao: bool = False):
    from shared.database import get_db
    if base_seg is None:
        base_seg = pregao_row.get("polling_seg_sessao", 30) if em_sessao else pregao_row.get("polling_seg_idle", 300)
    proximo = (datetime.now() + timedelta(seconds=base_seg)).isoformat()
    get_db().execute(
        "UPDATE radar_pregoes_monitorados SET proxima_consulta_em = ? WHERE id = ?",
        (proximo, pid),
    )
    get_db().commit()


def _marcar_credencial_erro(tenant_id: int, portal_id: int, msg: str):
    from shared.database import get_db
    status = "captcha" if "captcha" in msg.lower() else "expirado"
    get_db().execute(
        "UPDATE credenciais_portal SET status = ? WHERE tenant_id = ? AND portal_id = ?",
        (status, tenant_id, portal_id),
    )
    get_db().commit()


def atualizar_gauge_pregoes_ativos():
    from shared.database import get_db
    rows = get_db().execute(
        """SELECT po.slug, COUNT(*) AS n
           FROM radar_pregoes_monitorados p JOIN portais po ON po.id = p.portal_id
           WHERE p.silenciado = 0
           GROUP BY po.slug"""
    ).fetchall()
    for r in rows:
        RADAR_PREGOES_ATIVOS.labels(portal=r["slug"]).set(r["n"])
