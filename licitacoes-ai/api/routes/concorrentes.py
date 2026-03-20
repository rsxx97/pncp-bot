"""Rotas de concorrentes."""
import json
from fastapi import APIRouter

from api.deps import get_connection

router = APIRouter(prefix="/api/concorrentes", tags=["concorrentes"])


@router.get("")
def listar_concorrentes():
    """Retorna concorrentes do banco + fallback para config JSON."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM concorrentes WHERE ativo = 1").fetchall()

    result = []

    if rows:
        for r in rows:
            d = dict(r)
            for field in ("segmentos", "uf_atuacao"):
                if d.get(field) and isinstance(d[field], str):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        pass

            notas = (d.get("notas") or "").lower()
            if "agressiv" in notas:
                d["agressividade"] = "alta"
            elif "conservador" in notas or "baixa" in notas:
                d["agressividade"] = "baixa"
            else:
                d["agressividade"] = "media"

            d["lances_mes"] = 0
            d["desconto_medio"] = 0
            result.append(d)
    else:
        # Fallback: ler do config/concorrentes.json
        from pathlib import Path
        config_path = Path(__file__).parent.parent.parent / "config" / "concorrentes.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            for c in data.get("concorrentes", []):
                notas = (c.get("notas") or "").lower()
                agr = "alta" if "agressiv" in notas else "media"
                result.append({
                    "cnpj": c.get("cnpj", ""),
                    "nome_fantasia": c.get("nome_fantasia", ""),
                    "razao_social": c.get("razao_social", ""),
                    "segmentos": c.get("segmentos", []),
                    "notas": c.get("notas", ""),
                    "agressividade": agr,
                    "lances_mes": 0,
                    "desconto_medio": 0,
                })

    return result
