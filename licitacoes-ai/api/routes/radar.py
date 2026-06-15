"""REST do Radar: portais, credenciais, pregões monitorados, eventos."""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from api.deps import get_connection
from api.routes.auth import require_tenant
from radar.adapters.registry import ADAPTER_REGISTRY, get_adapter
from radar.credenciais import cifrar, cifrar_bytes, cifrar_dict
from radar.worker.monitor import tick_uma_vez

router = APIRouter(prefix="/api/radar", tags=["radar"])


# Campos UTC (gravados pelo SQLite via datetime('now') ou Python utcnow)
_UTC_FIELDS = {
    "criado_em", "atualizado_em", "ultima_consulta_em", "proxima_consulta_em",
    "monitorado_desde", "ultimo_login_em", "validade_ate", "lido_em",
}
# Campos BRT (retornados pela API SERPRO em horário de Brasília sem timezone)
_BRT_FIELDS = {
    "horario", "dataHora", "data_abertura", "data_encerramento",
}


def _adicionar_tz(s, suffix):
    """Adiciona offset/Z em string 'YYYY-MM-DD HH:MM:SS[.ffffff]'."""
    if not s or not isinstance(s, str):
        return s
    # Já tem timezone
    if "T" in s and (s.endswith("Z") or "+" in s[11:] or "-" in s[11:]):
        return s
    if len(s) >= 19 and s[4] == "-" and s[7] == "-":
        return s.replace(" ", "T", 1).split("+")[0].rstrip("Z") + suffix
    return s


def _normalizar_datas(obj):
    """Recursivamente normaliza campos de data: UTC fica Z; BRT fica -03:00."""
    if isinstance(obj, list):
        return [_normalizar_datas(x) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, str) and k in _UTC_FIELDS:
                out[k] = _adicionar_tz(v, "Z")
            elif isinstance(v, str) and k in _BRT_FIELDS:
                out[k] = _adicionar_tz(v, "-03:00")
            elif isinstance(v, (dict, list)):
                out[k] = _normalizar_datas(v)
            else:
                out[k] = v
        return out
    return obj


# ── Portais ──────────────────────────────────────────────────────────

@router.get("/portais")
def listar_portais(_tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM portais WHERE ativo = 1 ORDER BY nome").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        adapter_implementado = d["slug"] in {"pncp", "comprasnet"}
        requer_credencial = d["slug"] not in {"pncp", "comprasnet"} and d["tipo_integracao"] != "api_oficial"
        out.append({**d, "adapter_implementado": adapter_implementado, "requer_credencial": requer_credencial})
    return out


# ── Credenciais ──────────────────────────────────────────────────────

class CredencialIn(BaseModel):
    portal_slug: str
    login: str
    senha: str
    extra: dict | None = None


@router.put("/credenciais")
def upsert_credencial(body: CredencialIn, tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    portal = conn.execute("SELECT id FROM portais WHERE slug = ?", (body.portal_slug,)).fetchone()
    if not portal:
        raise HTTPException(404, "Portal não cadastrado")

    conn.execute(
        """INSERT INTO credenciais_portal (tenant_id, portal_id, login_cifrado, senha_cifrada, extra_cifrado, status)
           VALUES (?, ?, ?, ?, ?, 'ok')
           ON CONFLICT(tenant_id, portal_id) DO UPDATE SET
             login_cifrado = excluded.login_cifrado,
             senha_cifrada = excluded.senha_cifrada,
             extra_cifrado = excluded.extra_cifrado,
             status = 'ok'""",
        (tenant["id"], portal["id"], cifrar(body.login), cifrar(body.senha), cifrar_dict(body.extra)),
    )
    conn.commit()
    return {"ok": True}


@router.get("/credenciais")
def listar_credenciais(tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    rows = conn.execute(
        """SELECT po.slug, po.nome, c.status, c.ultimo_login_em, c.criado_em
           FROM credenciais_portal c JOIN portais po ON po.id = c.portal_id
           WHERE c.tenant_id = ?
           ORDER BY po.nome""",
        (tenant["id"],),
    ).fetchall()
    return _normalizar_datas([dict(r) for r in rows])


# IMPORTANTE: rotas estáticas (/credenciais/testar, /credenciais/pfx) precisam vir ANTES
# da rota com path param /credenciais/{portal_slug}, senão FastAPI matchea esta primeiro e
# retorna 405 Method Not Allowed.
@router.post("/credenciais/testar")
async def testar_credencial(tenant: dict = Depends(require_tenant)):
    """Faz 1 login + 1 fetch isolado pra validar credencial sem afetar pregões cadastrados."""
    import time as _t
    from radar.adapters.comprasnet_pfx import obter_sessao_autenticada

    conn = get_connection()
    row = conn.execute(
        """SELECT c.extra_cifrado FROM credenciais_portal c
           JOIN portais po ON po.id = c.portal_id
           WHERE c.tenant_id = ? AND po.slug = 'comprasnet'""",
        (tenant["id"],),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Nenhum certificado .pfx cadastrado pra ComprasNet. Faça upload primeiro.")

    from radar.credenciais import decifrar_dict
    extra = decifrar_dict(row["extra_cifrado"]) or {}
    pfx_b64 = extra.get("pfx_b64")
    pfx_senha = extra.get("pfx_senha")
    if not pfx_b64 or not pfx_senha:
        raise HTTPException(400, "Credencial sem pfx_b64 ou senha")

    t0 = _t.monotonic()
    try:
        sessao = await obter_sessao_autenticada(tenant["id"], pfx_b64, pfx_senha, forcar=True)
    except Exception as e:
        return {
            "ok": False, "fase": "exception",
            "erro": str(e)[:300],
            "duracao_seg": round(_t.monotonic() - t0, 1),
        }

    if not sessao:
        return {
            "ok": False, "fase": "sessao_none",
            "erro": "Login não retornou sessão (cap excedido, circuit breaker, captcha falhou ou IP banido)",
            "duracao_seg": round(_t.monotonic() - t0, 1),
        }

    cookies = sessao.get("cookies", [])
    cookies_cnet = [c for c in cookies if "cnetmobile" in (c.get("domain") or "") or "estaleiro" in (c.get("domain") or "")]
    return {
        "ok": True,
        "duracao_seg": round(_t.monotonic() - t0, 1),
        "cookies_total": len(cookies),
        "cookies_cnetmobile": len(cookies_cnet),
        "url_final": sessao.get("final_url", "")[:200],
    }


@router.delete("/credenciais/{portal_slug}")
def deletar_credencial(portal_slug: str, tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    conn.execute(
        """DELETE FROM credenciais_portal WHERE tenant_id = ?
           AND portal_id IN (SELECT id FROM portais WHERE slug = ?)""",
        (tenant["id"], portal_slug),
    )
    conn.commit()
    return {"ok": True}


# ── Status do 2captcha (necessário pra auth ao vivo no ComprasNet) ──

@router.get("/captcha/status")
def captcha_status(_tenant: dict = Depends(require_tenant)):
    try:
        from radar.adapters.comprasnet_pfx import captcha_status as _s
        return _s()
    except Exception as e:
        return {"configured": False, "provider": None, "error": str(e)}


# ── Certificado digital (.pfx) ───────────────────────────────────────

CNPJ_RE = re.compile(r"\b(\d{14})\b")


def _parse_pfx(pfx_bytes: bytes, senha: str) -> dict:
    """Parse + validação básica. Retorna {cnpj, nome, validade_ate, emissor}."""
    try:
        from cryptography.hazmat.primitives.serialization import pkcs12
    except ImportError as e:
        raise HTTPException(500, f"cryptography não instalada: {e}")

    try:
        priv_key, cert, _chain = pkcs12.load_key_and_certificates(
            pfx_bytes, senha.encode("utf-8") if senha else None,
        )
    except ValueError as e:
        raise HTTPException(400, f"Falha ao abrir .pfx: senha incorreta ou arquivo inválido ({e})")
    except Exception as e:
        raise HTTPException(400, f"Erro processando .pfx: {e}")

    if cert is None:
        raise HTTPException(400, "Arquivo .pfx não contém certificado")

    subject_str = cert.subject.rfc4514_string()
    cnpj_match = CNPJ_RE.search(subject_str)
    cnpj = cnpj_match.group(1) if cnpj_match else None

    nome = None
    for attr in cert.subject:
        if attr.oid._name in ("commonName", "CN"):
            nome = attr.value
            break

    validade = cert.not_valid_after
    agora = datetime.utcnow()
    if validade < agora:
        raise HTTPException(400, f"Certificado expirado em {validade.strftime('%d/%m/%Y')}")

    emissor = None
    for attr in cert.issuer:
        if attr.oid._name in ("commonName", "CN"):
            emissor = attr.value
            break

    return {
        "cnpj": cnpj,
        "nome": nome,
        "validade_ate": validade.isoformat(),
        "emissor": emissor,
        "dias_para_vencer": (validade - agora).days,
    }


@router.post("/credenciais/pfx")
async def upload_pfx(
    arquivo: UploadFile = File(...),
    senha: str = Form(...),
    portal_slug: str = Form("comprasnet"),
    tenant: dict = Depends(require_tenant),
):
    """Upload + validação + storage cifrado do certificado A1 (.pfx)."""
    pfx_bytes = await arquivo.read()
    if not pfx_bytes:
        raise HTTPException(400, "Arquivo vazio")
    if len(pfx_bytes) > 200_000:
        raise HTTPException(400, "Arquivo muito grande (>200KB) — não parece um .pfx")

    info = _parse_pfx(pfx_bytes, senha)

    conn = get_connection()
    portal = conn.execute("SELECT id FROM portais WHERE slug = ?", (portal_slug,)).fetchone()
    if not portal:
        raise HTTPException(404, f"Portal {portal_slug} não cadastrado")

    extra = {
        "tipo": "pfx",
        "pfx_b64": base64.b64encode(pfx_bytes).decode("ascii"),
        "pfx_senha": senha,
        "cnpj": info["cnpj"],
        "nome_titular": info["nome"],
        "validade_ate": info["validade_ate"],
        "emissor": info["emissor"],
    }

    conn.execute(
        """INSERT INTO credenciais_portal (tenant_id, portal_id, login_cifrado, senha_cifrada, extra_cifrado, status)
           VALUES (?, ?, ?, ?, ?, 'ok')
           ON CONFLICT(tenant_id, portal_id) DO UPDATE SET
             login_cifrado = excluded.login_cifrado,
             senha_cifrada = excluded.senha_cifrada,
             extra_cifrado = excluded.extra_cifrado,
             status = 'ok'""",
        (
            tenant["id"], portal["id"],
            cifrar(info["nome"] or "pfx"),
            cifrar("pfx"),
            cifrar_dict(extra),
        ),
    )
    conn.commit()

    return {
        "ok": True,
        "cnpj": info["cnpj"],
        "nome_titular": info["nome"],
        "validade_ate": info["validade_ate"],
        "dias_para_vencer": info["dias_para_vencer"],
        "emissor": info["emissor"],
        "portal_slug": portal_slug,
    }


# ── Pregões monitorados ──────────────────────────────────────────────

class PregaoMonitorarIn(BaseModel):
    portal_slug: str
    identificador: str
    tenant_empresa_id: int | None = None
    # Polling sustentável pra controlar custo de captcha — Elicita opera ~60-90s
    # 90s em sessão = 40 ticks/h, com cache compartilhado dilui entre clientes
    polling_seg_sessao: int = 90
    polling_seg_idle: int = 900


@router.get("/pregoes")
def listar_pregoes(
    tenant: dict = Depends(require_tenant),
    portal: str | None = Query(None),
    status: str | None = Query(None),
    busca: str | None = Query(None),
    favorito: bool | None = Query(None),
):
    conn = get_connection()
    where = ["p.tenant_id = ?"]
    params: list = [tenant["id"]]
    if portal:
        where.append("po.slug = ?")
        params.append(portal)
    if status:
        where.append("p.status = ?")
        params.append(status)
    if busca:
        where.append("(p.numero LIKE ? OR p.orgao LIKE ? OR p.objeto LIKE ?)")
        params.extend([f"%{busca}%"] * 3)
    if favorito is not None:
        where.append("p.favorito = ?")
        params.append(1 if favorito else 0)
    rows = conn.execute(
        f"""SELECT p.*, po.slug AS portal_slug, po.nome AS portal_nome
            FROM radar_pregoes_monitorados p JOIN portais po ON po.id = p.portal_id
            WHERE {' AND '.join(where)}
            ORDER BY p.status DESC, p.proxima_consulta_em ASC""",
        params,
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("snapshot_json"):
            try:
                d["snapshot"] = json.loads(d["snapshot_json"])
            except json.JSONDecodeError:
                d["snapshot"] = None
            del d["snapshot_json"]
        ev_rows = conn.execute(
            """SELECT id, tipo, criticidade, titulo, descricao, criado_em
               FROM radar_eventos WHERE pregao_monitorado_id = ? ORDER BY criado_em DESC LIMIT 5""",
            (d["id"],),
        ).fetchall()
        d["ultimos_eventos"] = [dict(e) for e in ev_rows]
        out.append(d)
    return _normalizar_datas(out)


@router.post("/pregoes")
async def monitorar_pregao(body: PregaoMonitorarIn, tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    portal = conn.execute("SELECT * FROM portais WHERE slug = ?", (body.portal_slug,)).fetchone()
    if not portal:
        raise HTTPException(404, "Portal não cadastrado")

    conn.execute(
        """INSERT INTO radar_pregoes_monitorados
           (tenant_id, tenant_empresa_id, portal_id, identificador, polling_seg_sessao, polling_seg_idle, proxima_consulta_em)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(tenant_id, portal_id, identificador) DO UPDATE SET
             silenciado = 0,
             polling_seg_sessao = excluded.polling_seg_sessao,
             polling_seg_idle = excluded.polling_seg_idle""",
        (
            tenant["id"], body.tenant_empresa_id, portal["id"], body.identificador,
            body.polling_seg_sessao, body.polling_seg_idle,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM radar_pregoes_monitorados WHERE tenant_id = ? AND portal_id = ? AND identificador = ?",
        (tenant["id"], portal["id"], body.identificador),
    ).fetchone()
    return dict(row)


class PregaoPorUasgIn(BaseModel):
    uasg: str
    numero: str
    ano: int
    tenant_empresa_id: int | None = None
    polling_seg_sessao: int = 90
    polling_seg_idle: int = 900


@router.post("/pregoes-por-uasg")
async def monitorar_pregao_por_uasg(body: PregaoPorUasgIn, tenant: dict = Depends(require_tenant)):
    """Cadastra pregão a partir de UASG + Número + Ano (sem precisar saber modalidade).

    Resolve via dadosabertos:
      - UASG -> nome do órgão / UF / CNPJ
      - (UASG, número, ano) -> modalidade + numeroControlePNCP + datas de abertura/encerramento
    """
    from radar.adapters.uasg_lookup import consultar_uasg
    import httpx
    from datetime import timedelta

    uasg = str(body.uasg).strip()
    numero = str(body.numero).strip()
    ano = int(body.ano)

    uasg_info = await consultar_uasg(uasg)
    if not uasg_info:
        raise HTTPException(404, f"UASG {uasg} não encontrada no dadosabertos")

    # Busca a compra entre todas modalidades (auto-detect)
    num_norm = numero.lstrip("0") or "0"
    # dadosabertos limita janela em 365 dias entre dataPublicacaoPncpInicial e Final
    janela_dias_passado = 340
    janela_dias_futuro = 20
    from datetime import datetime as _dt
    agora = _dt.now()
    dt_inicio = (agora - timedelta(days=janela_dias_passado)).strftime("%Y-%m-%d")
    dt_fim = (agora + timedelta(days=janela_dias_futuro)).strftime("%Y-%m-%d")

    compra = None
    mod_encontrada = None
    async with httpx.AsyncClient(timeout=30) as c:
        for mod in [5, 6, 3, 4, 20, 1, 2, 7]:
            try:
                r = await c.get(
                    "https://dadosabertos.compras.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
                    params={
                        "unidadeOrgaoCodigoUnidade": uasg,
                        "dataPublicacaoPncpInicial": dt_inicio,
                        "dataPublicacaoPncpFinal": dt_fim,
                        "codigoModalidade": mod,
                        "tamanhoPagina": 500,
                        "pagina": 1,
                    },
                    headers={"Accept": "application/json"},
                )
                if r.status_code != 200:
                    continue
                for it in r.json().get("resultado") or []:
                    item_num = str(it.get("numeroCompra") or "").lstrip("0") or "0"
                    item_ano = int(it.get("anoCompraPncp") or 0)
                    if item_num == num_norm and item_ano == ano:
                        compra = it
                        mod_encontrada = mod
                        break
                if compra:
                    break
            except httpx.HTTPError:
                continue

    if not compra:
        raise HTTPException(404, f"Compra {uasg}-{numero}-{ano} não encontrada nas modalidades comuns (5,6,3,4,20,1,2,7)")

    numero_pad = str(numero).zfill(5)
    identificador = f"{uasg}-{mod_encontrada}-{numero_pad}-{ano}"

    conn = get_connection()
    portal = conn.execute("SELECT * FROM portais WHERE slug = ?", ("comprasnet",)).fetchone()
    if not portal:
        raise HTTPException(500, "Portal comprasnet não cadastrado")

    conn.execute(
        """INSERT INTO radar_pregoes_monitorados
           (tenant_id, tenant_empresa_id, portal_id, identificador, orgao, objeto,
            polling_seg_sessao, polling_seg_idle, proxima_consulta_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(tenant_id, portal_id, identificador) DO UPDATE SET
             silenciado = 0,
             orgao = COALESCE(radar_pregoes_monitorados.orgao, excluded.orgao),
             objeto = COALESCE(radar_pregoes_monitorados.objeto, excluded.objeto),
             polling_seg_sessao = excluded.polling_seg_sessao,
             polling_seg_idle = excluded.polling_seg_idle,
             proxima_consulta_em = datetime('now')""",
        (
            tenant["id"], body.tenant_empresa_id, portal["id"], identificador,
            uasg_info.get("nomeUasg"),
            (compra.get("objetoCompra") or "")[:500],
            body.polling_seg_sessao, body.polling_seg_idle,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM radar_pregoes_monitorados WHERE tenant_id = ? AND portal_id = ? AND identificador = ?",
        (tenant["id"], portal["id"], identificador),
    ).fetchone()
    return {
        **dict(row),
        "uasg": uasg_info,
        "compra_meta": {
            "modalidade": compra.get("modalidadeNome"),
            "situacao": compra.get("situacaoCompraNomePncp"),
            "dataAberturaPropostaPncp": compra.get("dataAberturaPropostaPncp"),
            "dataEncerramentoPropostaPncp": compra.get("dataEncerramentoPropostaPncp"),
            "valorTotalEstimado": compra.get("valorTotalEstimado"),
            "numeroControlePNCP": compra.get("numeroControlePNCP"),
        },
    }


@router.delete("/pregoes/{pregao_id}")
def desmonitorar(pregao_id: int, tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    conn.execute(
        "DELETE FROM radar_pregoes_monitorados WHERE id = ? AND tenant_id = ?",
        (pregao_id, tenant["id"]),
    )
    conn.commit()
    return {"ok": True}


@router.post("/pregoes/{pregao_id}/silenciar")
def silenciar(pregao_id: int, silenciado: bool = True, tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    conn.execute(
        "UPDATE radar_pregoes_monitorados SET silenciado = ? WHERE id = ? AND tenant_id = ?",
        (1 if silenciado else 0, pregao_id, tenant["id"]),
    )
    conn.commit()
    return {"ok": True, "silenciado": silenciado}


@router.post("/pregoes/{pregao_id}/favorito")
def favoritar(pregao_id: int, favorito: bool = True, tenant: dict = Depends(require_tenant)):
    conn = get_connection()
    conn.execute(
        "UPDATE radar_pregoes_monitorados SET favorito = ? WHERE id = ? AND tenant_id = ?",
        (1 if favorito else 0, pregao_id, tenant["id"]),
    )
    conn.commit()
    return {"ok": True, "favorito": favorito}


@router.post("/tick")
async def forcar_tick(_tenant: dict = Depends(require_tenant)):
    """Força execução do tick agora (debug)."""
    return await tick_uma_vez()


@router.get("/pregoes/{pregao_id}/mensagens")
def historico_mensagens(pregao_id: int, tenant: dict = Depends(require_tenant)):
    """Histórico completo de mensagens detectadas pelo radar (de radar_eventos).
    Independe do snapshot atual — não perde mensagens mesmo se SERPRO retornar 204 transiente.
    """
    conn = get_connection()
    # Garante que o pregão pertence ao tenant
    pregao = conn.execute(
        "SELECT id, identificador, orgao, objeto, portal_id FROM radar_pregoes_monitorados WHERE id = ? AND tenant_id = ?",
        (pregao_id, tenant["id"]),
    ).fetchone()
    if not pregao:
        raise HTTPException(404, "Pregão não encontrado")

    rows = conn.execute(
        """SELECT id, tipo, criticidade, titulo, descricao, payload_json, criado_em
           FROM radar_eventos
           WHERE pregao_monitorado_id = ? AND tipo LIKE '%MENSAGEM%'
           ORDER BY criado_em DESC""",
        (pregao_id,),
    ).fetchall()

    mensagens = []
    for r in rows:
        d = dict(r)
        payload = {}
        if d.get("payload_json"):
            try: payload = json.loads(d["payload_json"])
            except Exception: payload = {}
        # payload pode ter "mensagem": {...} ou ser direto a msg
        msg = payload.get("mensagem") or payload
        mensagens.append({
            "evento_id": d["id"],
            "horario": msg.get("horario") or d["criado_em"],
            "remetente": msg.get("remetente") or ("pregoeiro" if "PREGOEIRO" in (d["tipo"] or "") else "fornecedor"),
            "texto": msg.get("texto") or d.get("descricao") or "",
            "categoria": msg.get("categoria"),
            "categoria_label": msg.get("categoria_label"),
            "criticidade": d.get("criticidade"),
            "detectado_em": d["criado_em"],
        })
    return _normalizar_datas({"pregao_id": pregao_id, "mensagens": mensagens, "total": len(mensagens)})


# ── Custo do 2captcha + Circuit Breaker ─────────────────────────────

@router.get("/custo")
def custo_captcha(tenant: dict = Depends(require_tenant)):
    """Gastos do tenant com 2captcha + status do circuit breaker."""
    from radar.adapters.comprasnet_pfx import CAP_DIARIO_SOLVES, CUSTO_POR_SOLVE_BRL
    conn = get_connection()

    hoje = conn.execute(
        """SELECT
             COALESCE(SUM(CASE WHEN evento = 'solve_ok' THEN valor_brl ELSE 0 END), 0) AS gasto,
             SUM(CASE WHEN evento = 'solve_ok' THEN 1 ELSE 0 END) AS solves_ok,
             SUM(CASE WHEN evento = 'solve_falhou' THEN 1 ELSE 0 END) AS solves_falhou
           FROM radar_custo_captcha
           WHERE tenant_id = ? AND criado_em > datetime('now', '-1 day')""",
        (tenant["id"],),
    ).fetchone()

    mes = conn.execute(
        """SELECT
             COALESCE(SUM(CASE WHEN evento = 'solve_ok' THEN valor_brl ELSE 0 END), 0) AS gasto,
             SUM(CASE WHEN evento = 'solve_ok' THEN 1 ELSE 0 END) AS solves_ok
           FROM radar_custo_captcha
           WHERE tenant_id = ? AND criado_em > datetime('now', '-30 days')""",
        (tenant["id"],),
    ).fetchone()

    cb = conn.execute(
        "SELECT falhas_consecutivas, bloqueado_ate, ultimo_erro FROM radar_circuit_breaker WHERE tenant_id = ?",
        (tenant["id"],),
    ).fetchone()

    ultimos = conn.execute(
        """SELECT evento, valor_brl, detalhe, criado_em FROM radar_custo_captcha
           WHERE tenant_id = ? ORDER BY criado_em DESC LIMIT 20""",
        (tenant["id"],),
    ).fetchall()

    return {
        "hoje": {
            "gasto_brl": round(hoje["gasto"] or 0, 2),
            "solves_ok": hoje["solves_ok"] or 0,
            "solves_falhou": hoje["solves_falhou"] or 0,
            "cap": CAP_DIARIO_SOLVES,
            "restante": max(0, CAP_DIARIO_SOLVES - (hoje["solves_ok"] or 0)),
        },
        "mes": {
            "gasto_brl": round(mes["gasto"] or 0, 2),
            "solves_ok": mes["solves_ok"] or 0,
        },
        "custo_por_solve_brl": CUSTO_POR_SOLVE_BRL,
        "circuit_breaker": {
            "ativo": bool(cb and cb["bloqueado_ate"] and cb["bloqueado_ate"] > __import__("datetime").datetime.now().isoformat()),
            "falhas_consecutivas": (cb["falhas_consecutivas"] if cb else 0),
            "bloqueado_ate": (cb["bloqueado_ate"] if cb else None),
            "ultimo_erro": (cb["ultimo_erro"] if cb else None),
        },
        "ultimos_eventos": _normalizar_datas([dict(r) for r in ultimos]),
    }


@router.post("/circuit-breaker/reset")
def resetar_circuit_breaker(tenant: dict = Depends(require_tenant)):
    """Limpa o circuit breaker (após trocar IP, por exemplo)."""
    conn = get_connection()
    conn.execute(
        "UPDATE radar_circuit_breaker SET falhas_consecutivas = 0, bloqueado_ate = NULL WHERE tenant_id = ?",
        (tenant["id"],),
    )
    conn.commit()
    return {"ok": True, "message": "Circuit breaker resetado"}


