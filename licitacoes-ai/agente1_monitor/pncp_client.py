"""Cliente REST da API PNCP com retry, paginação e fallback."""
import logging
import time
from datetime import date, timedelta

import httpx

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import PNCP_BASE_URL, ESTADO_FOCO
from shared.models import EditalResumo
from shared.utils import gerar_pncp_id, gerar_link_pncp

log = logging.getLogger("pncp_client")

MODALIDADES_NOME = {
    4: "Concorrência - Loss",
    5: "Concorrência",
    6: "Pregão Eletrônico",
    7: "Pregão Presencial",
    8: "Dispensa de Licitação",
}

# Rate limit: max 2 req/s
_last_request_time = 0.0


def _rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 0.5:
        time.sleep(0.5 - elapsed)
    _last_request_time = time.time()


def _get(url: str, params: dict, timeout: int = 90) -> dict | None:
    """GET com retry (3 tentativas) e rate limiting."""
    _rate_limit()
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, params=params)
                log.debug(f"GET {resp.url} → {resp.status_code}")

                if resp.status_code == 404:
                    return None
                if resp.status_code >= 500:
                    log.warning(f"Server error {resp.status_code} (tentativa {attempt+1}/3)")
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    return None

                resp.raise_for_status()
                text = resp.text.strip()
                if not text:
                    return None
                return resp.json()

        except httpx.TimeoutException:
            log.warning(f"Timeout (tentativa {attempt+1}/3)")
            if attempt < 2:
                time.sleep(10 * (attempt + 1))
        except httpx.HTTPError as e:
            log.error(f"HTTP error (tentativa {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
        except Exception as e:
            log.error(f"Erro inesperado: {e}")
            return None

    return None


def _item_to_edital(item: dict) -> EditalResumo:
    """Converte item da API PNCP para EditalResumo."""
    orgao = item.get("orgaoEntidade", {})
    unidade = item.get("unidadeOrgao", {})
    cnpj = orgao.get("cnpj", "")
    ano = item.get("anoCompra", "")
    seq = item.get("sequencialCompra", "")
    modalidade_cod = item.get("modalidadeId", item.get("codigoModalidadeContratacao"))

    return EditalResumo(
        pncp_id=gerar_pncp_id(cnpj, ano, seq),
        orgao_cnpj=cnpj,
        orgao_nome=orgao.get("razaoSocial", ""),
        objeto=item.get("objetoCompra", ""),
        valor_estimado=item.get("valorTotalEstimado"),
        data_publicacao=item.get("dataPublicacaoPncp", item.get("dataAtualizacao")),
        data_abertura=item.get("dataAberturaProposta"),
        data_encerramento=item.get("dataEncerramentoProposta"),
        modalidade=MODALIDADES_NOME.get(modalidade_cod, f"Código {modalidade_cod}"),
        modalidade_cod=modalidade_cod,
        uf=unidade.get("ufSigla", ""),
        municipio=unidade.get("municipioNome", ""),
        link_edital=gerar_link_pncp(cnpj, ano, seq),
        fonte="pncp",
    )


def buscar_editais(
    modalidades: list[int] = None,
    uf: str = None,
    dias_retroativos: int = 3,
    tam_pagina: int = 50,
) -> list[EditalResumo]:
    """Busca editais recentes no PNCP.

    Args:
        modalidades: Lista de códigos de modalidade (default: [5, 6])
        uf: UF para filtrar (None = usa config, "" = sem filtro)
        dias_retroativos: Quantos dias pra trás buscar
        tam_pagina: Itens por página

    Returns:
        Lista de EditalResumo
    """
    if modalidades is None:
        modalidades = [5, 6]  # Concorrência + Pregão Eletrônico

    if uf is None:
        uf = ESTADO_FOCO

    hoje = date.today()
    data_inicio = hoje - timedelta(days=dias_retroativos)

    url = f"{PNCP_BASE_URL}/contratacoes/publicacao"
    editais = []
    pncp_ids_vistos = set()

    for modalidade in modalidades:
        pagina = 1
        while True:
            params = {
                "dataInicial": data_inicio.strftime("%Y%m%d"),
                "dataFinal": hoje.strftime("%Y%m%d"),
                "codigoModalidadeContratacao": modalidade,
                "pagina": pagina,
                "tamanhoPagina": tam_pagina,
            }
            if uf:
                params["uf"] = uf

            dados = _get(url, params)
            if not dados:
                break

            itens = dados.get("data", [])
            if not itens:
                break

            for item in itens:
                try:
                    edital = _item_to_edital(item)
                    if edital.pncp_id not in pncp_ids_vistos:
                        pncp_ids_vistos.add(edital.pncp_id)
                        editais.append(edital)
                except Exception as e:
                    log.warning(f"Erro ao processar item: {e}")
                    continue

            total_paginas = dados.get("totalPaginas", 1)
            if pagina >= total_paginas:
                break
            pagina += 1

        log.info(f"Modalidade {modalidade} ({uf or 'BR'}): {pagina} página(s), {len(editais)} editais")

    return editais


def buscar_editais_nacional(
    modalidades: list[int] = None,
    dias_retroativos: int = 3,
    valor_minimo: float = 30_000_000,
    palavras_chave: list[str] = None,
) -> list[EditalResumo]:
    """Busca editais nacionais acima de um valor mínimo."""
    from shared.utils import contem_palavra_chave

    if palavras_chave is None:
        from config.settings import KEYWORDS_INTERESSE
        palavras_chave = KEYWORDS_INTERESSE

    todos = buscar_editais(
        modalidades=modalidades,
        uf="",  # Sem filtro de UF = nacional
        dias_retroativos=dias_retroativos,
    )

    filtrados = []
    for ed in todos:
        # Pula estado local
        if ed.uf == ESTADO_FOCO:
            continue
        # Filtro de valor
        if ed.valor_estimado is None or ed.valor_estimado < valor_minimo:
            continue
        # Filtro de keyword
        if contem_palavra_chave(ed.objeto, palavras_chave):
            filtrados.append(ed)

    log.info(f"Nacional: {len(filtrados)} editais acima de R$ {valor_minimo:,.0f}")
    return filtrados


def buscar_itens_compra(cnpj: str, ano: int, seq: int) -> list[dict]:
    """Busca itens de uma compra específica."""
    url = f"{PNCP_BASE_URL}/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
    dados = _get(url, {})
    if not dados:
        return []
    return dados if isinstance(dados, list) else dados.get("data", [])


def buscar_arquivos_compra(cnpj: str, ano: int, seq: int) -> list[dict]:
    """Busca documentos/arquivos de uma compra (PDFs do edital).

    A API PNCP retorna URLs como /pncp-api/v1/.../arquivos/N
    que servem o arquivo diretamente (PDF). O título geralmente
    contém o nome do arquivo original com extensão.

    Nota: endpoint de arquivos usa api/pncp/v1 (não api/consulta/v1).
    """
    # Endpoint de arquivos é diferente do de consulta
    PNCP_ARQUIVOS_URL = "https://pncp.gov.br/api/pncp/v1"
    url = f"{PNCP_ARQUIVOS_URL}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"
    dados = _get(url, {})
    if not dados:
        return []
    arquivos = dados if isinstance(dados, list) else dados.get("data", [])
    # Normalizar: garantir que todos tenham campo 'titulo' e 'url'
    for arq in arquivos:
        if not arq.get("url") and arq.get("uri"):
            arq["url"] = arq["uri"]
    return arquivos


def buscar_edital_por_id(cnpj: str, ano: int, seq: int) -> EditalResumo | None:
    """Busca um edital específico por CNPJ/ano/seq."""
    url = f"{PNCP_BASE_URL}/orgaos/{cnpj}/compras/{ano}/{seq}"
    dados = _get(url, {})
    if not dados:
        return None
    try:
        return _item_to_edital(dados)
    except Exception as e:
        log.error(f"Erro ao processar edital {cnpj}/{ano}/{seq}: {e}")
        return None


def buscar_editais_por_texto(query: str, tam_pagina: int = 20, paginas: int = 1) -> list[dict]:
    """Busca editais no PNCP por texto livre (objeto, orgao, etc).

    Usa o endpoint /api/search/ do portal PNCP.
    Retorna lista de dicts com dados do edital.
    """
    url = "https://pncp.gov.br/api/search/"
    all_items = []
    try:
        with httpx.Client(timeout=30) as client:
            for pag in range(1, paginas + 1):
                _rate_limit()
                resp = client.get(url, params={
                    "q": query,
                    "tipos_documento": "edital",
                    "pagina": pag,
                    "tam_pagina": tam_pagina,
                })
                if resp.status_code != 200:
                    log.warning(f"Search PNCP retornou {resp.status_code}")
                    break
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break
                # Converte item_url em pncp_id
                for it in items:
                    item_url = it.get("item_url", "")
                    parts = item_url.replace("/compras/", "").split("/")
                    if len(parts) == 3:
                        it["pncp_id"] = f"{parts[0]}-{parts[1]}-{parts[2]}"
                all_items.extend(items)
                total = data.get("total", 0)
                if pag * tam_pagina >= total:
                    break
        log.info(f"Search PNCP '{query}': {len(all_items)} resultados em {paginas} página(s)")
    except Exception as e:
        log.error(f"Erro na busca PNCP: {e}")
    return all_items


def buscar_editais_por_cnpj_orgao(
    cnpj_orgao: str,
    dias_retroativos: int = 90,
    tam_pagina: int = 50,
) -> list[EditalResumo]:
    """Busca editais de um órgão específico pelo CNPJ.

    Útil para encontrar licitações de um órgão quando se tem o CNPJ/UASG.
    """
    hoje = date.today()
    data_inicio = hoje - timedelta(days=dias_retroativos)

    # Remove formatação do CNPJ (pontos, barras, traços)
    cnpj_limpo = cnpj_orgao.replace(".", "").replace("/", "").replace("-", "").strip()

    url = f"{PNCP_BASE_URL}/contratacoes/publicacao"
    editais = []
    pncp_ids_vistos = set()

    pagina = 1
    while True:
        params = {
            "dataInicial": data_inicio.strftime("%Y%m%d"),
            "dataFinal": hoje.strftime("%Y%m%d"),
            "cnpj": cnpj_limpo,
            "pagina": pagina,
            "tamanhoPagina": tam_pagina,
        }

        dados = _get(url, params)
        if not dados:
            break

        itens = dados.get("data", [])
        if not itens:
            break

        for item in itens:
            try:
                edital = _item_to_edital(item)
                if edital.pncp_id not in pncp_ids_vistos:
                    pncp_ids_vistos.add(edital.pncp_id)
                    editais.append(edital)
            except Exception as e:
                log.warning(f"Erro ao processar item: {e}")
                continue

        total_paginas = dados.get("totalPaginas", 1)
        if pagina >= total_paginas:
            break
        pagina += 1

    log.info(f"Busca por CNPJ {cnpj_limpo}: {len(editais)} editais encontrados")
    return editais
