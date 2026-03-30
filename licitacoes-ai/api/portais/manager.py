"""Gerenciador multi-portal — tenta cada portal e retorna o melhor resultado."""
import logging
from .base import ResultadoPortal
from .pncp import PNCPConector
from .comprasgov import ComprasGovConector

log = logging.getLogger("portal.manager")

# Registra todos os conectores disponíveis
CONECTORES = [
    PNCPConector(),
    ComprasGovConector(),
]

# Portais futuros (placeholder)
PORTAIS_NAO_IMPLEMENTADOS = {
    "comprasrj": "ComprasRJ — integração pendente",
    "licitacoes-e": "Licitações-e (BB) — integração pendente",
    "comprasbr": "ComprasBR — integração pendente",
    "bll": "BLL Compras — integração pendente",
    "bnc": "Bolsa Nacional de Compras — integração pendente",
    "compraspublicas": "Portal de Compras Públicas — integração pendente",
}


def buscar_resultado_multiportal(pncp_id: str, portal_hint: str = None, uasg: str = None) -> dict:
    """Busca resultado do pregão em múltiplos portais.

    Args:
        pncp_id: ID do edital no formato CNPJ-ANO-SEQ
        portal_hint: Portal preferido (comprasnet, comprasrj, etc.)
        uasg: UASG do órgão (para ComprasGov)

    Returns:
        Dict com resultados por portal e melhor resultado
    """
    parts = pncp_id.split("-")
    if len(parts) < 3 or pncp_id.startswith("MANUAL"):
        return {
            "melhor": ResultadoPortal(portal="nenhum", erro="ID manual — busque o edital real no PNCP primeiro").__dict__,
            "portais": {},
            "erros": ["Edital manual não tem integração automática"],
        }

    cnpj, ano, seq = parts[0], parts[1], parts[2]
    numero = seq  # Simplificação

    resultados = {}
    erros = []

    for conector in CONECTORES:
        try:
            log.info(f"Buscando em {conector.nome}...")
            result = conector.buscar_dados_pregao(
                cnpj=cnpj, ano=int(ano), seq=int(seq),
                uasg=uasg, numero=numero,
            )
            resultados[conector.nome] = result

            if result.erro:
                erros.append(f"{conector.nome}: {result.erro}")
                log.warning(f"{conector.nome}: {result.erro}")
            else:
                log.info(f"{conector.nome}: {len(result.classificacao)} empresas, status={result.status_pregao}")

        except Exception as e:
            erro = f"{conector.nome}: Erro de integração — {str(e)}"
            erros.append(erro)
            log.error(erro)
            resultados[conector.nome] = ResultadoPortal(portal=conector.nome, erro=str(e))

    # Se nenhum conector retornou classificação, tenta scraping do ComprasGov
    tem_classificacao = any(r.classificacao for r in resultados.values() if not r.erro)
    if not tem_classificacao and uasg:
        try:
            from .comprasgov_scraper import scrape_pregao, extrair_numero_pregao
            log.info(f"Tentando scraping ComprasGov para UASG {uasg}...")
            num_pregao = seq
            scrape_result = scrape_pregao(uasg, num_pregao, ano)

            if scrape_result.get("classificacao"):
                # Converte para ResultadoPortal
                res_scrape = ResultadoPortal(portal="ComprasGov (Scraper)")
                res_scrape.classificacao = scrape_result["classificacao"]
                res_scrape.vencedor_nome = scrape_result.get("vencedor_nome")
                res_scrape.vencedor_valor = scrape_result.get("vencedor_valor")
                res_scrape.total_participantes = scrape_result.get("total_participantes", 0)
                res_scrape.status_pregao = scrape_result.get("status", "")
                res_scrape.mensagens = scrape_result.get("mensagens", [])
                res_scrape.lances = scrape_result.get("lances", [])
                resultados["ComprasGov (Scraper)"] = res_scrape
                log.info(f"Scraper encontrou {len(res_scrape.classificacao)} empresas")
            elif scrape_result.get("erro"):
                erros.append(f"ComprasGov Scraper: {scrape_result['erro']}")
            else:
                erros.append("ComprasGov Scraper: Nenhum dado encontrado na página")

        except Exception as e:
            erros.append(f"ComprasGov Scraper: {str(e)}")
            log.error(f"Scraper falhou: {e}")

    # Verifica portais não implementados
    if portal_hint and portal_hint.lower() in PORTAIS_NAO_IMPLEMENTADOS:
        msg = PORTAIS_NAO_IMPLEMENTADOS[portal_hint.lower()]
        erros.append(f"{msg}")

    # Seleciona melhor resultado (o que tem mais dados)
    melhor = None
    for nome, res in resultados.items():
        if not res.erro and res.classificacao:
            if melhor is None or len(res.classificacao) > len(melhor.classificacao):
                melhor = res

    if melhor is None:
        melhor = ResultadoPortal(portal="nenhum", erro="Nenhum portal retornou resultado. " + "; ".join(erros))

    return {
        "melhor": melhor.__dict__,
        "portais": {k: v.__dict__ for k, v in resultados.items()},
        "erros": erros,
    }


def listar_portais_status() -> list:
    """Lista todos os portais e seu status."""
    portais = []
    for conector in CONECTORES:
        try:
            ok = conector.disponivel()
            portais.append({"nome": conector.nome, "status": "online" if ok else "offline", "integrado": True})
        except:
            portais.append({"nome": conector.nome, "status": "erro", "integrado": True})

    for key, desc in PORTAIS_NAO_IMPLEMENTADOS.items():
        portais.append({"nome": key, "status": "pendente", "integrado": False, "descricao": desc})

    return portais
