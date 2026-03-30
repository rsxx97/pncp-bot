"""Search PNCP API to find real IDs for manual editais."""
import sys
import time
import httpx

sys.path.insert(0, "C:/Users/Bruno Campos/Desktop/Nova pasta/licitacoes-ai")

PNCP_BASE_URL = "https://pncp.gov.br/api/consulta/v1"
SEARCH_URL = "https://pncp.gov.br/api/search/"
TIMEOUT = 60

# Manual editais to match
MANUAL_EDITAIS = [
    {
        "name": "PMDC | INFRAESTRUTURA URBANA",
        "valor": 8_600_000,
        "uf": "RJ",
        "queries": [
            "infraestrutura urbana duque de caxias",
            "PMDC infraestrutura",
            "duque caxias infraestrutura",
            "prefeitura duque caxias obra urbana",
        ],
    },
    {
        "name": "CMI/RJ | SEGURANCA E MEDICINA DO TRABALHO",
        "valor": 280_000,
        "uf": "RJ",
        "queries": [
            "seguranca medicina trabalho rio de janeiro",
            "CMI seguranca trabalho",
            "medicina trabalho RJ",
            "seguranca trabalho rio janeiro",
        ],
    },
    {
        "name": "SEFAZ/RJ | LIMPEZA E CONSERVACAO",
        "valor": 3_200_000,
        "uf": "RJ",
        "queries": [
            "limpeza conservacao SEFAZ rio janeiro",
            "sefaz rj limpeza",
            "secretaria fazenda rio janeiro limpeza",
            "SEFAZ limpeza conservacao",
        ],
    },
    {
        "name": "REURB | REGULARIZACAO FUNDIARIA URBANA",
        "valor": 1_100_000,
        "uf": "RJ",
        "queries": [
            "regularizacao fundiaria urbana rio janeiro",
            "REURB regularizacao fundiaria",
            "regularizacao fundiaria RJ",
            "fundiaria urbana rio de janeiro",
        ],
    },
    {
        "name": "CASS | LIMPEZA E CONSERVACAO",
        "valor": 740_000,
        "uf": "RJ",
        "queries": [
            "limpeza conservacao CASS",
            "CASS limpeza rio janeiro",
            "CASS limpeza conservacao RJ",
            "CASS rio janeiro",
        ],
    },
    {
        "name": "PREFEITURA DE BELFORD ROXO | LIMPEZA URBANA",
        "valor": 6_900_000,
        "uf": "RJ",
        "queries": [
            "limpeza urbana belford roxo",
            "belford roxo limpeza",
            "prefeitura belford roxo limpeza urbana",
            "belford roxo conservacao limpeza",
        ],
    },
]


def search_pncp(query, tam_pagina=15):
    """Search PNCP with generous timeout."""
    time.sleep(0.6)
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(SEARCH_URL, params={
                "q": query,
                "tipos_documento": "edital",
                "pagina": 1,
                "tam_pagina": tam_pagina,
            })
            if resp.status_code != 200:
                print(f"    [WARN] Search returned {resp.status_code}")
                return []
            data = resp.json()
            items = data.get("items", [])
            for it in items:
                item_url = it.get("item_url", "")
                parts = item_url.replace("/compras/", "").split("/")
                if len(parts) == 3:
                    it["pncp_id"] = f"{parts[0]}-{parts[1]}-{parts[2]}"
            return items
    except Exception as e:
        print(f"    [ERROR] Search '{query}': {e}")
        return []


def fetch_edital_details(cnpj, ano, seq):
    """Fetch full edital details to get valor_estimado."""
    time.sleep(0.6)
    url = f"{PNCP_BASE_URL}/orgaos/{cnpj}/compras/{ano}/{seq}"
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return {
                "valor_estimado": data.get("valorTotalEstimado"),
                "orgao_nome": data.get("orgaoEntidade", {}).get("razaoSocial", ""),
                "objeto": data.get("objetoCompra", ""),
                "uf": data.get("unidadeOrgao", {}).get("ufSigla", ""),
                "municipio": data.get("unidadeOrgao", {}).get("municipioNome", ""),
            }
    except Exception as e:
        print(f"    [ERROR] Fetch {cnpj}/{ano}/{seq}: {e}")
        return None


def value_match_pct(val_manual, val_api):
    if val_api is None or val_api == 0:
        return None
    return abs(val_manual - val_api) / val_manual * 100


def search_for_edital(edital_info):
    print(f"\n{'='*80}")
    print(f"SEARCHING: {edital_info['name']}")
    print(f"Target valor: R$ {edital_info['valor']:,.2f} | UF: {edital_info['uf']}")
    print(f"{'='*80}")

    all_candidates = {}

    for query in edital_info["queries"]:
        print(f"\n  Query: '{query}'")
        results = search_pncp(query)

        rj_count = 0
        for r in results:
            uf = r.get("uf", "")
            pncp_id = r.get("pncp_id", "")

            if uf != edital_info["uf"]:
                continue

            rj_count += 1

            if pncp_id in all_candidates:
                continue

            all_candidates[pncp_id] = {
                "pncp_id": pncp_id,
                "orgao": r.get("orgao_nome", ""),
                "desc": (r.get("description", "") or "")[:120],
                "municipio": r.get("municipio_nome", ""),
                "valor_search": r.get("valor_global"),
                "valor_api": None,
                "match_pct": None,
                "query_found": query,
            }

        print(f"  -> {len(results)} results, {rj_count} from RJ")

    print(f"\n  {len(all_candidates)} unique RJ candidates. Fetching details...")

    for pncp_id, info in all_candidates.items():
        parts = pncp_id.split("-")
        if len(parts) != 3:
            continue

        cnpj, ano, seq = parts[0], parts[1], parts[2]
        details = fetch_edital_details(cnpj, int(ano), int(seq))
        if details:
            info["valor_api"] = details["valor_estimado"]
            info["match_pct"] = value_match_pct(edital_info["valor"], details["valor_estimado"])
            if details["orgao_nome"]:
                info["orgao"] = details["orgao_nome"]
            if details["objeto"]:
                info["desc"] = details["objeto"][:120]
            if details["municipio"]:
                info["municipio"] = details["municipio"]

    # Sort by match quality
    sorted_candidates = sorted(
        all_candidates.values(),
        key=lambda x: x["match_pct"] if x["match_pct"] is not None else 9999,
    )

    print(f"\n  --- RESULTS (sorted by value proximity) ---")
    matches = []
    for c in sorted_candidates:
        match_str = f"{c['match_pct']:.1f}%" if c['match_pct'] is not None else "N/A"
        valor_str = f"R$ {c['valor_api']:,.2f}" if c['valor_api'] else "N/A"
        is_match = c['match_pct'] is not None and c['match_pct'] <= 50

        print(f"  {'>>>' if is_match else '   '} pncp_id: {c['pncp_id']}")
        print(f"      orgao: {c['orgao']}")
        print(f"      objeto: {c['desc']}")
        print(f"      municipio: {c['municipio']}")
        print(f"      valor: {valor_str} (diff: {match_str}){'  *** MATCH ***' if is_match else ''}")
        print()

        if is_match:
            matches.append(c)

    return matches


def main():
    all_matches = {}

    for edital in MANUAL_EDITAIS:
        matches = search_for_edital(edital)
        all_matches[edital["name"]] = matches

    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    for name, matches in all_matches.items():
        print(f"\n{name}:")
        if matches:
            for m in matches:
                valor_str = f"R$ {m['valor_api']:,.2f}" if m['valor_api'] else "N/A"
                print(f"  -> pncp_id: {m['pncp_id']}")
                print(f"     orgao: {m['orgao']}")
                print(f"     valor: {valor_str} (diff: {m['match_pct']:.1f}%)")
                print(f"     objeto: {m['desc']}")
        else:
            print("  -> NO MATCH FOUND")

    matched_count = sum(1 for m in all_matches.values() if m)
    print(f"\n{'='*80}")
    print(f"Matched: {matched_count} / {len(MANUAL_EDITAIS)}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
