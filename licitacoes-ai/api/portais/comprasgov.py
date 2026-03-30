"""Conector ComprasGov (ComprasNet) — Portal de compras do governo federal."""
import logging
import httpx
from .base import PortalConector, ResultadoPortal

log = logging.getLogger("portal.comprasgov")
CONTRATOS_API = "https://contratos.comprasnet.gov.br/api/contrato"


class ComprasGovConector(PortalConector):
    nome = "ComprasGov"

    def buscar_dados_pregao(self, uasg=None, numero=None, ano=None, **kw) -> ResultadoPortal:
        """Busca dados do pregão no ComprasGov."""
        result = ResultadoPortal(portal=self.nome)

        if not uasg:
            result.erro = "UASG não informada. Para órgãos federais, informe a UASG."
            return result

        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                # Busca contratos da UG
                resp = client.get(f"{CONTRATOS_API}/ug?co_uasg={uasg}")
                if resp.status_code != 200:
                    result.erro = f"ComprasGov HTTP {resp.status_code}"
                    return result

                contratos = resp.json()
                if not isinstance(contratos, list):
                    result.erro = "Resposta inesperada da API ComprasGov"
                    return result

                # Filtra contratos relacionados ao pregão
                pregao_num = f"{numero}/{ano}" if numero and ano else None
                relevantes = []

                for c in contratos:
                    licitacao = c.get("licitacao_associada", {})
                    num_licit = licitacao.get("numero", "")
                    modalidade = licitacao.get("modalidade", {}).get("descricao", "")

                    # Match por número ou por recência
                    if pregao_num and pregao_num in num_licit:
                        relevantes.append(c)
                    elif "Pregão" in modalidade and ano and str(ano) in num_licit:
                        relevantes.append(c)

                if relevantes:
                    for c in relevantes:
                        contratado = c.get("contratado", {})
                        result.classificacao.append({
                            "posicao": len(result.classificacao) + 1,
                            "empresa": contratado.get("nome", ""),
                            "cnpj": contratado.get("cnpj_cpf_idgener", ""),
                            "valor_proposta": None,
                            "valor_lance_final": c.get("valor_inicial"),
                            "habilitado": True,
                        })

                    if result.classificacao:
                        result.vencedor_nome = result.classificacao[0]["empresa"]
                        result.vencedor_cnpj = result.classificacao[0]["cnpj"]
                        result.vencedor_valor = result.classificacao[0]["valor_lance_final"] or 0
                        result.total_participantes = len(result.classificacao)
                        result.status_pregao = "contratado"
                else:
                    result.erro = f"Nenhum contrato encontrado para pregão {pregao_num or 'N/I'} na UASG {uasg}. Pode não ter sido homologado ainda."

        except httpx.TimeoutException:
            result.erro = "API ComprasGov lenta (timeout). Tente novamente."
        except Exception as e:
            result.erro = f"Erro ComprasGov: {str(e)}"

        return result

    def buscar_resultado(self, **kw) -> ResultadoPortal:
        return self.buscar_dados_pregao(**kw)

    def disponivel(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.head("https://contratos.comprasnet.gov.br")
                return resp.status_code < 500
        except:
            return False
