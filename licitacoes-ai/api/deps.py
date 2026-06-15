"""Dependências compartilhadas da API."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import get_db, init_db


def get_connection():
    """Retorna conexão SQLite."""
    return get_db()


def tenant_filter_sql(tenant: dict | None) -> tuple[str, list]:
    """Cláusula WHERE para filtrar por tenant (SaaS — isolamento estrito).

    - Sem auth ou super_admin (operador): vê tudo
    - Tenant comum (cliente): SÓ os editais do próprio tenant. Nada compartilhado.
    """
    if not tenant or tenant.get("role") == "super_admin":
        return "1=1", []
    return "tenant_id = ?", [tenant["id"]]
