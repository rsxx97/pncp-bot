"""Coleta e análise de histórico de lances do PNCP."""
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import inserir_lance, get_lances_por_cnpj, get_lances_por_compra, get_db
from agente1_monitor.pncp_client import buscar_editais

log = logging.getLogger("historico_lances")

PNCP_RESULTADO_URL = "https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}/resultados"


def coletar_historico_concorrente(cnpj: str, termo: str = "limpeza",
                                   paginas: int = 3) -> list[dict]:
    """Busca licitações onde o concorrente participou via PNCP.

    Nota: A API PNCP não tem endpoint direto de busca por fornecedor.
    Esta função busca licitações pelo termo e depois filtra por CNPJ nos resultados.
    Para coleta mais completa, usar dados do Portal da Transparência.
    """
    lances_encontrados = []

    try:
        editais = buscar_editais(
            termo=termo,
            uf="",
            pagina=1,
            tam_pagina=50,
        )

        for edital in editais[:100]:  # Limita para performance
            pncp_id = edital.get("pncp_id", "")
            # Check if we already have lances for this compra
            existentes = get_lances_por_compra(pncp_id)
            if existentes:
                # Verifica se o CNPJ está nos lances existentes
                for lance in existentes:
                    if lance.get("cnpj_fornecedor") == cnpj:
                        lances_encontrados.append(lance)
                continue

    except Exception as e:
        log.error(f"Erro ao coletar histórico de {cnpj}: {e}")

    return lances_encontrados


def salvar_lances(lances: list[dict]):
    """Salva lista de lances no banco, evitando duplicatas."""
    count = 0
    for lance in lances:
        try:
            # Verifica duplicata
            existentes = get_lances_por_compra(lance.get("pncp_id_compra", ""))
            ja_existe = any(
                l["cnpj_fornecedor"] == lance.get("cnpj_fornecedor")
                for l in existentes
            )
            if not ja_existe:
                inserir_lance(lance)
                count += 1
        except Exception as e:
            log.error(f"Erro ao salvar lance: {e}")
    return count


def analisar_historico_cnpj(cnpj: str) -> dict:
    """Analisa padrão de lances de um CNPJ.

    Returns:
        Dict com estatísticas: desconto médio, agressividade, etc.
    """
    lances = get_lances_por_cnpj(cnpj, limit=100)

    if not lances:
        return {
            "cnpj": cnpj,
            "total_participacoes": 0,
            "desconto_medio_pct": 0,
            "desconto_max_pct": 0,
            "taxa_vitoria_pct": 0,
            "agressividade": "desconhecida",
            "valor_medio_lance": 0,
        }

    total = len(lances)
    vitorias = sum(1 for l in lances if l.get("vencedor"))
    taxa_vitoria = (vitorias / total * 100) if total > 0 else 0

    # Calcular descontos (se tiver valor de referência)
    descontos = []
    valores = []
    for l in lances:
        valor = l.get("valor_lance") or l.get("valor_proposta_final")
        if valor and valor > 0:
            valores.append(valor)

    valor_medio = sum(valores) / len(valores) if valores else 0

    # Classificar agressividade
    if taxa_vitoria >= 60:
        agressividade = "alta"
    elif taxa_vitoria >= 30:
        agressividade = "media"
    else:
        agressividade = "baixa"

    return {
        "cnpj": cnpj,
        "total_participacoes": total,
        "vitorias": vitorias,
        "desconto_medio_pct": round(sum(descontos) / len(descontos), 2) if descontos else 0,
        "desconto_max_pct": round(max(descontos), 2) if descontos else 0,
        "taxa_vitoria_pct": round(taxa_vitoria, 2),
        "agressividade": agressividade,
        "valor_medio_lance": round(valor_medio, 2),
    }
