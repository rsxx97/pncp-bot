"""Carrega variáveis de ambiente e define constantes do sistema."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
EDITAIS_DIR = DATA_DIR / "editais"
CCTS_DIR = DATA_DIR / "ccts"
DB_PATH = DATA_DIR / "licitacoes.db"

# LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-20250414")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# PNCP
PNCP_BASE_URL = "https://pncp.gov.br/api/consulta/v1"

# Configurações de negócio
ESTADO_FOCO = os.getenv("ESTADO_FOCO", "RJ")
SCORE_MINIMO = int(os.getenv("SCORE_MINIMO", "60"))
INTERVALO_MONITOR_MINUTOS = int(os.getenv("INTERVALO_MONITOR_MINUTOS", "30"))

# CNAEs das empresas do grupo
CNAES_GRUPO = {
    "manutec": ["8121-4/00", "8111-7/00", "8130-3/00", "7810-8/00"],
    "blue": ["8211-3/00", "7810-8/00", "8219-9/99"],
    "miami": ["8012-9/00", "8011-1/01", "8020-0/01"],
}

# Palavras-chave de interesse (objeto da licitação)
KEYWORDS_INTERESSE = [
    "limpeza", "conservação", "asseio", "facilities", "predial",
    "terceirização", "mão de obra", "apoio administrativo", "apoio operacional",
    "recepção", "recepcionista", "portaria", "copeiragem",
    "vigilância", "segurança", "vigia", "controlador de acesso",
    "brigada", "bombeiro civil",
    "motorista", "condutor", "transporte",
    "manutenção predial", "elétrica", "hidráulica",
    "ascensorista", "garçom", "motoboy", "office boy",
    "técnico administrativo", "arquivologia", "arquivista",
    "jardinagem", "paisagismo", "zeladoria",
    "engenharia", "construção", "reforma", "obra",
    "coleta de resíduos", "destinação de resíduos", "transporte de resíduos",
    "resíduos sólidos", "manejo de resíduos",
]

# Palavras-chave de exclusão (não nos interessa)
KEYWORDS_EXCLUSAO = [
    "software", "equipamento médico", "hospitalar",
    "medicamento", "ambulância", "odontológico",
    "laboratorial", "informática", "tecnologia da informação",
    "alimentação escolar", "merenda",
    "limpeza de piscina", "material de limpeza",
    "materiais de limpeza",
]

# Custos Claude API (USD por 1M tokens) — para estimativa
CLAUDE_PRICING = {
    "input_per_mtok": 3.0,
    "output_per_mtok": 15.0,
}
