"""Conector base para portais de licitação."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResultadoPortal:
    """Dados retornados por um portal de licitação."""
    portal: str = ""
    status_pregao: str = ""  # aberto, em_disputa, encerrado, homologado
    mensagens: list = field(default_factory=list)  # [{remetente, mensagem, horario}]
    lances: list = field(default_factory=list)  # [{empresa, cnpj, valor, horario, rodada, nosso}]
    classificacao: list = field(default_factory=list)  # [{posicao, empresa, cnpj, valor_proposta, valor_lance_final, habilitado}]
    vencedor_nome: str = ""
    vencedor_cnpj: str = ""
    vencedor_valor: float = 0
    total_participantes: int = 0
    erro: str = ""  # Se deu erro na integração


class PortalConector:
    """Interface base para conectores de portais."""

    nome: str = "Base"

    def buscar_dados_pregao(self, uasg: str, numero: str, ano: str, **kwargs) -> ResultadoPortal:
        """Busca dados do pregão no portal."""
        raise NotImplementedError

    def buscar_resultado(self, uasg: str, numero: str, ano: str, **kwargs) -> ResultadoPortal:
        """Busca resultado final do pregão."""
        raise NotImplementedError

    def disponivel(self) -> bool:
        """Verifica se o portal está acessível."""
        return True
