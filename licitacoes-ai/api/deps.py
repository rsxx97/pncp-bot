"""Dependências compartilhadas da API."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import get_db, init_db


def get_connection():
    """Retorna conexão SQLite."""
    return get_db()


def tenant_filter_sql(tenant: dict | None) -> tuple[str, list]:
    """Cláusula WHERE para filtrar por tenant.

    - Sem auth ou super_admin: sem filtro
    - Tenant comum: editais do próprio tenant + globais (tenant_id NULL)
    """
    if not tenant or tenant.get("role") == "super_admin":
        return "1=1", []
    return "(tenant_id = ? OR tenant_id IS NULL)", [tenant["id"]]
