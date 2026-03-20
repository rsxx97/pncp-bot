"""Dependências compartilhadas da API."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import get_db, init_db

def get_connection():
    """Retorna conexão SQLite."""
    return get_db()
