"""Adapter ComprasNet (Compras.gov.br) — API pública dadosabertos.

Identificador esperado: "UASG-MOD-NUM-ANO" (ex: 160471-6-00067-2024).
  UASG = Unidade Administrativa de Serviços Gerais (federal).
  MOD  = código de modalidade ComprasNet (5=Pregão Eletrônico, 6=Dispensa,
         3=Concorrência, 4=Pregão Presencial, 20=RDC, ...).
         Use 0 (zero) ou "auto" para detectar automaticamente — o adapter
         faz fanout em paralelo nas modalidades comuns e retorna a primeira
         que casar com UASG + número + ano.
  NUM  = número da compra
  ANO  = ano

Estratégia: bate em /modulo-contratacoes (Lei 14.133) filtrando por UASG
em janela ampla e seleciona o item com numeroCompra/anoCompraPncp/codigoModalidade
correspondentes. Fallback no /modulo-legado (Lei 8.666) se não achar.

Sem credenciais. Não captura lances ao vivo nem mensagens — pra isso o
ComprasNet/SERPRO só expõe via scraping autenticado.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from radar.adapters.base import (
    NotFoundError,
    PortalAdapter,
    PregaoSnapshot,
    RateLimitError,
)

log = logging.getLogger("radar.comprasnet")

BASE = "https://dadosabertos.compras.gov.br"
URL_14133 = f"{BASE}/modulo-contratacoes/1_consultarContratacoes_PNCP_14133"
URL_LEGADO = f"{BASE}/modulo-legado/3_consultarPregoes"

JANELA_PASSADO_DIAS = 120
JANELA_FUTURO_DIAS = 60

# Modalidades ComprasNet a sondar em paralelo quando mod=0 (auto-detect).
# Ordem aproximada de frequência atual no federal.
MODALIDADES_AUTO = [5, 6, 3, 4, 20, 1, 2, 7]


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _normalizar_num(s: str | int) -> str:
    """Remove zeros à esquerda pra comparar 00067 == 67."""
    try:
        return str(int(str(s).strip()))
    except (ValueError, TypeError):
        return str(s).strip()


def _classificar_status(item: dict, agora: datetime) -> tuple[str, str | None]:
    """Retorna (status, fase). Heurística baseada em datas + flags."""
    if item.get("contratacaoExcluida"):
        return "encerrado", None

    abertura = _parse_dt(item.get("dataAberturaPropostaPncp"))
    encerramento = _parse_dt(item.get("dataEncerramentoPropostaPncp"))
    tem_resultado = bool(item.get("existeResultado"))
    homologado = item.get("valorTotalHomologado") is not None

    if homologado or (tem_resultado and encerramento and agora > encerramento + timedelta(hours=1)):
        return "encerrado", "homologacao"

    if encerramento and agora > encerramento:
        if tem_resultado:
            return "encerrado", "homologacao"
        return "em_sessao", "habilitacao"

    if abertura and agora >= abertura:
        return "em_sessao", "lances"

    return "agendado", None


class ComprasnetAdapter(PortalAdapter):
    slug = "comprasnet"
    nome = "Compras.gov.br (ComprasNet)"
    requer_credencial = False
    suporta_lances_proprios = False

    async def fetch_pregao(self, identificador: str) -> PregaoSnapshot:
        uasg, mod, num, ano = self._split_identificador(identificador)
        agora = datetime.now()
        dt_inicio = (agora - timedelta(days=JANELA_PASSADO_DIAS)).strftime("%Y-%m-%d")
        dt_fim = (agora + timedelta(days=JANELA_FUTURO_DIAS)).strftime("%Y-%m-%d")

        import os as _os
        client_kwargs = dict(timeout=20, headers={"Accept": "application/json"})
        proxy = _os.environ.get("RADAR_PROXY_URL")
        if proxy:
            client_kwargs["proxy"] = proxy
        async with httpx.AsyncClient(**client_kwargs) as client:
            if mod == 0:
                item = await self._buscar_14133_auto(client, uasg, num, ano, dt_inicio, dt_fim)
            else:
                item = await self._buscar_14133(client, uasg, mod, num, ano, dt_inicio, dt_fim)
            if item is None:
                item = await self._buscar_legado(client, uasg, mod, num, ano, dt_inicio, dt_fim)

        if item is None:
            raise NotFoundError(f"compra {identificador} não encontrada na janela de {JANELA_PASSADO_DIAS}d passado / {JANELA_FUTURO_DIAS}d futuro")

        snap = self._parse(identificador, item, agora)

        # Enriquecimento live — ESTRATÉGIA:
        # 1. /public/v1/* via hCaptcha local (R$ 0) — funciona durante janela ativa do SERPRO
        # 2. .pfx (sessão autenticada gov.br) — captura msgs em QUALQUER fase, inclusive pós-sessão,
        #    desde que o pregão ainda exista no SERPRO. Como agora resolve hCaptcha gov.br localmente
        #    (sem custo 2captcha), pode rodar sempre que público não trouxer chat e cert disponível.
        if snap.status == "em_sessao":
            await self._enriquecer_via_captcha(snap, identificador)

        if (
            self._tem_pfx()
            and not snap.mensagens
            and snap.status != "encerrado"
            and not self._pfx_em_circuit_breaker()
        ):
            await self._enriquecer_pfx(snap, identificador)

        return snap

    def _pfx_em_circuit_breaker(self) -> bool:
        """Checa se o .pfx desse tenant tá pausado por circuit breaker — evita disparar Playwright."""
        creds = self.credenciais or {}
        tenant_id = creds.get("_tenant_id")
        if not tenant_id:
            return False
        try:
            from shared.database import get_db
            r = get_db().execute(
                "SELECT pausado_ate FROM radar_circuit_breaker WHERE tenant_id = ? AND portal_slug = ?",
                (int(tenant_id), self.slug),
            ).fetchone()
            if not r or not r["pausado_ate"]:
                return False
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S") < r["pausado_ate"]
        except Exception:
            return False

    async def _enriquecer_via_captcha(self, snap: PregaoSnapshot, identificador: str) -> None:
        """Puxa lances + mensagens via API pública usando 2captcha."""
        try:
            from radar.adapters.comprasnet_chat import fetch_live
        except ImportError as e:
            log.warning(f"módulo comprasnet_chat indisponível: {e}")
            return
        creds = self.credenciais or {}
        cnpj_proprio = creds.get("cnpj") if creds.get("tipo") == "pfx" else None
        try:
            live = await fetch_live(identificador, cnpj_proprio=cnpj_proprio)
        except Exception as e:
            log.warning(f"falha no fetch live de {identificador}: {e}")
            return
        if not live:
            return
        if live.get("lances"):
            snap.lances = live["lances"]
        if live.get("mensagens"):
            snap.mensagens = live["mensagens"]
        if live.get("melhor_lance") is not None:
            snap.melhor_lance = live["melhor_lance"]
            snap.melhor_lance_cnpj = live.get("melhor_lance_cnpj")
        if live.get("minha_posicao") is not None:
            snap.minha_posicao = live["minha_posicao"]
            snap.meu_melhor_lance = live.get("meu_melhor_lance")

    def _tem_pfx(self) -> bool:
        return bool(self.credenciais and self.credenciais.get("tipo") == "pfx" and self.credenciais.get("pfx_b64"))

    async def _enriquecer_pfx(self, snap: PregaoSnapshot, identificador: str) -> None:
        """Puxa lances + mensagens + fase via API autenticada SERPRO (mTLS)."""
        try:
            from radar.adapters.comprasnet_pfx import fetch_live_pfx
        except ImportError as e:
            log.warning(f"módulo comprasnet_pfx indisponível: {e}")
            return
        creds = self.credenciais or {}
        try:
            live = await fetch_live_pfx(
                tenant_id=int(creds.get("_tenant_id", 0)),
                pfx_b64=creds["pfx_b64"],
                senha=creds.get("pfx_senha", ""),
                compra_id=identificador,
                cnpj_proprio=creds.get("cnpj"),
            )
        except Exception as e:
            log.warning(f"falha no fetch .pfx de {identificador}: {e}")
            return
        if not live:
            return
        if live.get("fase"):
            snap.fase = live["fase"]
        if live.get("lances"):
            snap.lances = live["lances"]
        if live.get("mensagens"):
            snap.mensagens = live["mensagens"]
        if live.get("melhor_lance") is not None:
            snap.melhor_lance = live["melhor_lance"]
            snap.melhor_lance_cnpj = live.get("melhor_lance_cnpj")
        if live.get("minha_posicao") is not None:
            snap.minha_posicao = live["minha_posicao"]
            snap.meu_melhor_lance = live.get("meu_melhor_lance")

    async def _enriquecer_live(self, snap: PregaoSnapshot, identificador: str) -> None:
        """Tenta puxar lances/mensagens via Playwright. Falha silenciosa: já temos o status."""
        try:
            from radar.adapters.comprasnet_live import extrair_live
        except ImportError as e:
            log.warning(f"playwright indisponível, seguindo só com status: {e}")
            return
        try:
            live = await extrair_live(identificador)
        except Exception as e:
            log.warning(f"falha no scrape live de {identificador}: {e}")
            return
        if live.get("fase"):
            snap.fase = live["fase"]
        if live.get("lances"):
            snap.lances = live["lances"]
        if live.get("mensagens"):
            snap.mensagens = live["mensagens"]
        if live.get("melhor_lance") is not None:
            snap.melhor_lance = live["melhor_lance"]
            snap.melhor_lance_cnpj = live.get("melhor_lance_cnpj")

    def _split_identificador(self, ident: str) -> tuple[str, int, str, int]:
        parts = ident.split("-")
        if len(parts) == 3:
            # Forma compacta: UASG-NUM-ANO (auto-detect modalidade)
            uasg, num, ano = parts[0].strip(), parts[1].strip(), parts[2].strip()
            mod = "0"
        elif len(parts) >= 4:
            uasg, mod, num, ano = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        else:
            raise NotFoundError(f"identificador inválido: {ident} (esperado UASG-MOD-NUM-ANO ou UASG-NUM-ANO)")

        if mod.lower() in ("auto", ""):
            mod = "0"
        try:
            mod_int = int(mod)
            ano_int = int(ano)
        except ValueError as e:
            raise NotFoundError(f"identificador inválido: {ident} ({e})") from e
        return uasg, mod_int, num, ano_int

    async def _buscar_14133_auto(
        self, client: httpx.AsyncClient, uasg: str, num: str, ano: int,
        dt_inicio: str, dt_fim: str,
    ) -> dict | None:
        """Fanout em paralelo nas modalidades comuns. Retorna o 1º match."""
        async def _try(mod: int):
            try:
                return await self._buscar_14133(client, uasg, mod, num, ano, dt_inicio, dt_fim)
            except RateLimitError:
                return None  # ignora rate limit individual; outras modalidades podem ter sucesso
            except Exception as e:
                log.warning(f"auto-detect modalidade {mod} falhou: {e}")
                return None

        results = await asyncio.gather(*[_try(m) for m in MODALIDADES_AUTO])
        for item in results:
            if item is not None:
                return item
        return None

    async def _buscar_14133(
        self, client: httpx.AsyncClient, uasg: str, mod: int, num: str, ano: int,
        dt_inicio: str, dt_fim: str,
    ) -> dict | None:
        params = {
            "unidadeOrgaoCodigoUnidade": uasg,
            "dataPublicacaoPncpInicial": dt_inicio,
            "dataPublicacaoPncpFinal": dt_fim,
            "codigoModalidade": mod,
            "tamanhoPagina": 500,
            "pagina": 1,
        }
        try:
            r = await client.get(URL_14133, params=params)
        except httpx.HTTPError as e:
            raise RateLimitError(f"erro de rede ComprasNet: {e}", retry_em=15) from e

        if r.status_code == 429:
            raise RateLimitError("ComprasNet 429", retry_em=60)
        if r.status_code >= 500:
            raise RateLimitError(f"ComprasNet HTTP {r.status_code}", retry_em=30)
        if r.status_code != 200:
            log.warning(f"14133 retornou {r.status_code}: {r.text[:200]}")
            return None

        data = r.json()
        return self._encontrar(data.get("resultado") or [], num, ano)

    async def _buscar_legado(
        self, client: httpx.AsyncClient, uasg: str, mod: int, num: str, ano: int,
        dt_inicio: str, dt_fim: str,
    ) -> dict | None:
        params = {
            "coUasg": uasg,
            "numero": _normalizar_num(num),
            "dt_data_edital_inicial": dt_inicio,
            "dt_data_edital_final": dt_fim,
            "tamanhoPagina": 500,
            "pagina": 1,
        }
        try:
            r = await client.get(URL_LEGADO, params=params)
        except httpx.HTTPError as e:
            raise RateLimitError(f"erro de rede ComprasNet legado: {e}", retry_em=15) from e

        if r.status_code == 429:
            raise RateLimitError("ComprasNet legado 429", retry_em=60)
        if r.status_code >= 500:
            raise RateLimitError(f"ComprasNet legado HTTP {r.status_code}", retry_em=30)
        if r.status_code != 200:
            log.warning(f"legado retornou {r.status_code}: {r.text[:200]}")
            return None

        return self._encontrar(r.json().get("resultado") or [], num, ano)

    def _encontrar(self, lista: list[dict], num: str, ano: int) -> dict | None:
        num_n = _normalizar_num(num)
        for item in lista:
            item_num = _normalizar_num(item.get("numeroCompra") or item.get("nu_aviso") or item.get("numero") or "")
            item_ano = item.get("anoCompraPncp") or item.get("ano_pregao") or item.get("ano")
            if item_num == num_n and str(item_ano) == str(ano):
                return item
        return None

    def _parse(self, identificador: str, data: dict[str, Any], agora: datetime) -> PregaoSnapshot:
        status, fase = _classificar_status(data, agora)
        return PregaoSnapshot(
            portal_slug=self.slug,
            identificador=identificador,
            numero=str(data.get("numeroCompra") or data.get("numeroControlePNCP") or ""),
            orgao=(
                data.get("orgaoEntidadeRazaoSocial")
                or data.get("unidadeOrgaoNomeUnidade")
                or data.get("nm_orgao")
            ),
            objeto=data.get("objetoCompra") or data.get("ds_objeto"),
            data_abertura=_parse_dt(data.get("dataAberturaPropostaPncp") or data.get("dt_abertura_proposta")),
            data_encerramento=_parse_dt(data.get("dataEncerramentoPropostaPncp") or data.get("dt_encerramento_proposta")),
            status=status,
            fase=fase,
            valor_estimado=data.get("valorTotalEstimado") or data.get("vl_total_estimado"),
            raw=data,
        )
