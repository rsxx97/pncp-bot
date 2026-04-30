"""Levantamento direto no PNCP de editais de obra/reforma/manutenção predial em SC+RJ.

Consulta a API search do PNCP em tempo real (não usa banco local), aplica os
mesmos filtros do bot_obra (exclusões + score) e reporta quantos disparariam.

Uso: python core/skills/levantamento_obra_pncp.py
"""
import json
import sys
import time
from pathlib import Path

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "licitacoes-ai"))
from bot_obra import _eh_falso_obra, _eh_manutencao, _score_obra

KEYWORDS_BUSCA = [
    "obra", "reforma", "construção",
    "manutenção predial", "manutenção preventiva", "manutenção corretiva",
    "ampliação", "edificação", "pavimentação",
    "engenharia civil", "infraestrutura", "elevador",
    "ar condicionado", "climatização", "drenagem",
]
UFS = ["SC", "RJ"]


def buscar_pncp(termo: str, uf: str, max_paginas: int = 10) -> list:
    """Search PNCP por termo, status aberto. Filtro UF do PNCP é falho — corrige na main()."""
    resultados = []
    for pagina in range(1, max_paginas + 1):
        try:
            r = httpx.get(
                "https://pncp.gov.br/api/search/",
                params={
                    "q": termo,
                    "tipos_documento": "edital",
                    "status": "recebendo_proposta",
                    "uf": uf,
                    "pagina": pagina,
                    "tam_pagina": 50,
                },
                timeout=20,
            )
            if r.status_code != 200:
                break
            data = r.json()
            items = data.get("items") or data.get("results") or []
            if not items:
                break
            resultados.extend(items)
            total = data.get("total", 0)
            if pagina * 50 >= total:
                break
            time.sleep(0.3)
        except Exception:
            break
    return resultados


def montar_pncp_id(item: dict) -> str | None:
    """Extrai cnpj-ano-seq do item de busca."""
    cnpj = item.get("orgao_cnpj") or item.get("cnpj") or ""
    ano = item.get("ano") or ""
    seq = item.get("numero_sequencial") or item.get("numeroSequencial") or item.get("sequencial") or ""
    if cnpj and ano and seq:
        return f"{cnpj}-{ano}-{seq}"
    return None


def main():
    achados = {}
    print(f"Buscando {len(KEYWORDS_BUSCA)} keywords × {len(UFS)} UFs no PNCP search...")
    descartados_uf = 0
    for uf_alvo in UFS:
        for kw in KEYWORDS_BUSCA:
            items = buscar_pncp(kw, uf_alvo)
            válidos_uf = 0
            for it in items:
                # PNCP search pode retornar items fora da UF — confirma manualmente
                uf_real = (it.get("uf") or "").upper()
                if uf_real not in UFS:
                    descartados_uf += 1
                    continue
                válidos_uf += 1
                pid = montar_pncp_id(it)
                if not pid:
                    continue
                if pid not in achados:
                    achados[pid] = {
                        "uf": uf_real,
                        "objeto": it.get("description") or it.get("title") or "",
                        "modalidade": it.get("modalidade_licitacao_nome") or "",
                        "orgao": it.get("orgao_nome") or "",
                        "link": "https://pncp.gov.br/app/editais/" + (it.get("item_url", "").replace("/compras/", "")),
                        "data_fim": it.get("data_fim_vigencia") or "",
                        "valor": it.get("valor_global"),
                        "kws": set(),
                    }
                achados[pid]["kws"].add(kw)
            print(f"  {uf_alvo:2s} | '{kw:25s}' → {len(items):3d} items ({válidos_uf} na UF correta)")
            time.sleep(0.3)
    print(f"\n  ⚠️ Descartados por UF errada (filtro PNCP falho): {descartados_uf}")

    print(f"\n=== {len(achados)} editais únicos encontrados ===\n")

    # Aplica filtros do bot_obra
    aceitos = []
    rejeitados_falso = 0
    rejeitados_score = 0
    for pid, info in achados.items():
        obj = info["objeto"]
        if _eh_falso_obra(obj):
            rejeitados_falso += 1
            continue
        if not (_eh_manutencao(obj) or _score_obra(obj) >= 2):
            rejeitados_score += 1
            continue
        aceitos.append((pid, info))

    print(f"  Aceitos: {len(aceitos)}")
    print(f"  Rejeitados (exclusão TI/veículo/internet): {rejeitados_falso}")
    print(f"  Rejeitados (score baixo): {rejeitados_score}")

    print(f"\n=== Aceitos por UF ===")
    sc = sum(1 for _, i in aceitos if i["uf"] == "SC")
    rj = sum(1 for _, i in aceitos if i["uf"] == "RJ")
    print(f"  SC: {sc} | RJ: {rj}")

    # Salva pra possível disparo
    out = Path(__file__).parent.parent.parent / "data" / "levantamento_obra.json"
    out.parent.mkdir(exist_ok=True)
    payload = [
        {
            "pncp_id": pid,
            "uf": i["uf"],
            "orgao": i["orgao"],
            "modalidade": i["modalidade"],
            "objeto": i["objeto"][:300],
            "link": i["link"],
            "score": _score_obra(i["objeto"]),
            "manutencao": _eh_manutencao(i["objeto"]),
            "kws_descoberta": sorted(i["kws"]),
        }
        for pid, i in aceitos
    ]
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo em: {out}")


if __name__ == "__main__":
    main()
