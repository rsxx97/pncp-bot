"""Pydantic models compartilhados entre os agentes."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EditalResumo(BaseModel):
    """Dados básicos de um edital vindo da API PNCP."""
    pncp_id: str
    orgao_cnpj: str = ""
    orgao_nome: str = ""
    objeto: str
    valor_estimado: Optional[float] = None
    data_publicacao: Optional[str] = None
    data_abertura: Optional[str] = None
    data_encerramento: Optional[str] = None
    modalidade: Optional[str] = None
    modalidade_cod: Optional[int] = None
    uf: str = ""
    municipio: Optional[str] = None
    link_edital: Optional[str] = None
    fonte: str = "pncp"


class ClassificacaoEdital(BaseModel):
    """Resultado da classificação do Agente 1."""
    pncp_id: str
    score: int = Field(ge=0, le=100)
    justificativa: str
    empresa_sugerida: str
    tags: list[str] = []
    alertas: list[str] = []


class PostoTrabalho(BaseModel):
    """Um posto de trabalho extraído do edital."""
    funcao: str
    quantidade: int = 1
    jornada: str = "44h"
    escolaridade_minima: str = "medio"
    descricao_atividades: str = ""


class AnaliseEdital(BaseModel):
    """Resultado da análise do Agente 2."""
    pncp_id: str
    parecer: str  # "go", "nogo", "go_com_ressalvas"
    motivo: str
    requisitos_habilitacao: list[str] = []
    atestados_exigidos: list[str] = []
    riscos: list[str] = []
    oportunidades: list[str] = []
    valor_estimado: Optional[float] = None
    qtd_postos: Optional[int] = None
    postos: list[PostoTrabalho] = []
    regime_contratacao: Optional[str] = None
    prazo_contrato_meses: Optional[int] = None
    cct_aplicavel: Optional[str] = None
    local_prestacao: Optional[str] = None
    adjudicacao: Optional[str] = None
    criterio_julgamento: Optional[str] = None


class CheckViabilidade(BaseModel):
    """Resultado de um check do viability_checker."""
    check: str
    status: str  # "ok", "falha", "alerta"
    detalhe: str


class CenarioBDI(BaseModel):
    """Um cenário do simulador de BDI."""
    cenario: str
    ci_pct: float
    lucro_pct: float
    tributos_pct: float
    bdi_pct: float
    valor_mensal: float
    valor_global: float
    desconto_sobre_referencia_pct: Optional[float] = None
    acima_inexequibilidade: bool = True


class LanceSugerido(BaseModel):
    """Resultado da análise competitiva do Agente 4."""
    pncp_id: str
    lance_minimo: float
    lance_sugerido: float
    lance_maximo: float
    margem_sugerida_pct: float
    justificativa: str
    concorrentes_esperados: list[str] = []


class ConcorrentePerfil(BaseModel):
    """Perfil resumido de um concorrente."""
    cnpj: str
    nome: str
    desconto_medio_pct: float = 0
    desconto_max_pct: float = 0
    agressividade: str = "media"  # baixa, media, alta
    total_participacoes: int = 0
    taxa_vitoria_pct: float = 0
