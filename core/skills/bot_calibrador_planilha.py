"""Bot Calibrador de Planilha — aprende com editais homologados.

Pipeline:
1. Lê editais com valor_homologado preenchido (resultado disponível)
2. Compara vs valor_estimado (desconto observado)
3. Agrupa por nicho/UF/modalidade
4. Calcula estatísticas (média, mediana, p25/p75, n)
5. Persiste em data/calibracao_nicho.json
6. Atualiza BDI/margem sugerida (consumível pelo agente3_precificador)

Roda 1x ao dia (custoso de CPU mas barato — sem chamadas externas).
"""
import json
import logging
import sqlite3
import sys
import statistics
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
LICITACOES_AI = ROOT / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
try:
    from config.settings import DB_PATH
except Exception:
    DB_PATH = LICITACOES_AI / "data" / "licitacoes.db"

OUT = ROOT / "data" / "calibracao_nicho.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_calibrador")


def _stats(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0}
    valores_sorted = sorted(valores)
    return {
        "n": len(valores),
        "media": round(statistics.mean(valores), 4),
        "mediana": round(statistics.median(valores), 4),
        "p25": round(statistics.quantiles(valores_sorted, n=4)[0], 4) if len(valores) >= 4 else None,
        "p75": round(statistics.quantiles(valores_sorted, n=4)[2], 4) if len(valores) >= 4 else None,
        "min": round(min(valores), 4),
        "max": round(max(valores), 4),
    }


def calibrar() -> dict:
    if not Path(DB_PATH).exists():
        log.warning(f"DB não existe: {DB_PATH}")
        return {}

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row

    # Considera editais nos últimos 12 meses com valor_proposta E valor_estimado preenchidos
    cutoff = (datetime.now() - timedelta(days=365)).isoformat()
    rows = conn.execute("""
        SELECT pncp_id, nicho, uf, modalidade, orgao_nome, objeto,
               valor_estimado, valor_proposta, bdi_percentual, margem_percentual
          FROM editais
         WHERE valor_estimado > 0
           AND valor_proposta > 0
           AND date(created_at) >= date(?)
    """, (cutoff,)).fetchall()
    log.info(f"{len(rows)} editais com valor_estimado + valor_proposta")

    # Agrupa por nicho
    por_nicho = {}
    por_nicho_uf = {}
    todos_descontos = []

    for r in rows:
        ve = r["valor_estimado"]
        vp = r["valor_proposta"]
        if not (ve and vp) or ve <= 0:
            continue
        desconto = (ve - vp) / ve  # 0..1

        nicho = (r["nicho"] or "outros").lower()
        uf = (r["uf"] or "").upper()

        por_nicho.setdefault(nicho, []).append(desconto)
        por_nicho_uf.setdefault(f"{nicho}|{uf}", []).append(desconto)
        todos_descontos.append(desconto)

    # BDI e margem (campo direto)
    bdi_por_nicho = {}
    margem_por_nicho = {}
    for r in rows:
        nicho = (r["nicho"] or "outros").lower()
        if r["bdi_percentual"] and r["bdi_percentual"] > 0:
            bdi_por_nicho.setdefault(nicho, []).append(r["bdi_percentual"])
        if r["margem_percentual"] and r["margem_percentual"] > 0:
            margem_por_nicho.setdefault(nicho, []).append(r["margem_percentual"])

    out = {
        "gerado_em": datetime.now().isoformat(),
        "fonte": "tabela editais (licitacoes-ai/data/licitacoes.db)",
        "total_amostras": len(todos_descontos),
        "desconto_global": _stats(todos_descontos),
        "desconto_por_nicho": {n: _stats(v) for n, v in por_nicho.items()},
        "desconto_por_nicho_uf": {k: _stats(v) for k, v in por_nicho_uf.items()},
        "bdi_por_nicho": {n: _stats(v) for n, v in bdi_por_nicho.items()},
        "margem_por_nicho": {n: _stats(v) for n, v in margem_por_nicho.items()},
    }

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"✓ {OUT.name}: {len(todos_descontos)} amostras, "
             f"{len(por_nicho)} nichos, "
             f"{len(por_nicho_uf)} pares nicho×UF")

    # Resumo amigável no console
    print("\n=== Calibração por nicho (desconto médio observado) ===")
    for nicho in sorted(por_nicho, key=lambda n: -len(por_nicho[n]))[:15]:
        s = _stats(por_nicho[nicho])
        if s["n"] >= 3:
            print(f"  {nicho:<22} n={s['n']:>4}  desconto médio={s['media']*100:>5.2f}%  mediana={s['mediana']*100:>5.2f}%")

    conn.close()
    return out


if __name__ == "__main__":
    calibrar()
