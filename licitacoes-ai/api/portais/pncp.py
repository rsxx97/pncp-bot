"""Conector PNCP — Portal Nacional de Contratações Públicas."""
import logging
import httpx
from .base import PortalConector, ResultadoPortal

log = logging.getLogger("portal.pncp")
BASE = "https://pncp.gov.br/api/consulta/v1"


class PNCPConector(PortalConector):
    nome = "PNCP"

    def buscar_dados_pregao(self, uasg=None, numero=None, ano=None, cnpj=None, seq=None, **kw) -> ResultadoPortal:
        """Busca dados básicos da compra no PNCP."""
        if not cnpj or not ano or not seq:
            return ResultadoPortal(portal=self.nome, erro="Necessário cnpj, ano e seq")

        result = ResultadoPortal(portal=self.nome)
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(f"{BASE}/orgaos/{cnpj}/compras/{ano}/{seq}")
                if resp.status_code != 200:
                    result.erro = f"HTTP {resp.status_code}"
                    return result

                data = resp.json()
                situacao = data.get("situacaoCompraNome", "")
                result.status_pregao = situacao

                # Busca itens + resultados
                resp_itens = client.get(f"{BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens")
                if resp_itens.status_code == 200:
                    itens = resp_itens.json()
                    empresas = {}

                    for item in itens:
                        num = item.get("numeroItem")
                        if not num:
                            continue

                        resp_res = client.get(f"{BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{num}/resultados")
                        if resp_res.status_code == 200:
                            for r in resp_res.json():
                                key = r.get("cnpjFornecedor", r.get("nomeRazaoSocialFornecedor", ""))
                                if key not in empresas:
                                    empresas[key] = {
                                        "empresa": r.get("nomeRazaoSocialFornecedor", ""),
                                        "cnpj": r.get("cnpjFornecedor", ""),
                                        "valor": 0,
                                    }
                                empresas[key]["valor"] += r.get("valorTotalHomologado", 0) or 0

                    if empresas:
                        ranking = sorted(empresas.values(), key=lambda x: x["valor"])
                        for i, emp in enumerate(ranking, 1):
                            result.classificacao.append({
                                "posicao": i,
                                "empresa": emp["empresa"],
                                "cnpj": emp["cnpj"],
                                "valor_proposta": None,
                                "valor_lance_final": emp["valor"],
                                "habilitado": True,
                            })
                        result.vencedor_nome = ranking[0]["empresa"]
                        result.vencedor_cnpj = ranking[0]["cnpj"]
                        result.vencedor_valor = ranking[0]["valor"]
                        result.total_participantes = len(ranking)

        except httpx.TimeoutException:
            result.erro = "API do PNCP lenta (timeout). Tente novamente."
        except Exception as e:
            result.erro = f"Erro PNCP: {str(e)}"

        return result

    def buscar_resultado(self, **kw) -> ResultadoPortal:
        return self.buscar_dados_pregao(**kw)

    def disponivel(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{BASE}/contratacoes/publicacao?pagina=1&tamanhoPagina=1&dataInicial=20260101&dataFinal=20260101&codigoModalidadeContratacao=6")
                return resp.status_code == 200
        except:
            return False
