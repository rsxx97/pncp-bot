"""Profiling de concorrentes a partir do cadastro e histórico."""
import json
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import BASE_DIR
from shared.database import listar_concorrentes, upsert_concorrente
from agente4_competitivo.historico_lances import analisar_historico_cnpj

log = logging.getLogger("concorrente_profiler")


def carregar_concorrentes_config() -> list[dict]:
    """Carrega concorrentes do arquivo de configuração."""
    config_path = BASE_DIR / "config" / "concorrentes.json"
    if not config_path.exists():
        log.warning("Arquivo concorrentes.json não encontrado")
        return []

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("concorrentes", [])


def sincronizar_concorrentes():
    """Importa concorrentes do config para o banco."""
    concorrentes = carregar_concorrentes_config()
    count = 0

    for c in concorrentes:
        cnpj = c.get("cnpj", "")
        if not cnpj:
            continue

        upsert_concorrente(
            cnpj=cnpj,
            razao_social=c.get("razao_social", ""),
            nome_fantasia=c.get("nome_fantasia", ""),
            segmentos=c.get("segmentos", []),
            uf_atuacao=c.get("uf_atuacao", []),
            notas=c.get("notas", ""),
        )
        count += 1

    log.info(f"{count} concorrentes sincronizados")
    return count


def profiler_concorrente(cnpj: str) -> dict:
    """Gera perfil completo de um concorrente.

    Combina dados cadastrais + histórico de lances.
    """
    # Dados cadastrais
    concorrentes = listar_concorrentes()
    cadastro = next((c for c in concorrentes if c.get("cnpj") == cnpj), {})

    # Histórico
    historico = analisar_historico_cnpj(cnpj)

    return {
        "cnpj": cnpj,
        "razao_social": cadastro.get("razao_social", ""),
        "nome_fantasia": cadastro.get("nome_fantasia", ""),
        "segmentos": cadastro.get("segmentos", []),
        "uf_atuacao": cadastro.get("uf_atuacao", []),
        "notas": cadastro.get("notas", ""),
        "historico": historico,
        "agressividade": historico.get("agressividade", "desconhecida"),
        "taxa_vitoria_pct": historico.get("taxa_vitoria_pct", 0),
        "desconto_medio_pct": historico.get("desconto_medio_pct", 0),
    }


def listar_concorrentes_por_segmento(segmento: str) -> list[dict]:
    """Lista concorrentes que atuam em um segmento específico."""
    concorrentes = listar_concorrentes()
    resultado = []

    for c in concorrentes:
        segs = c.get("segmentos", [])
        if isinstance(segs, str):
            segs = [segs]
        seg_lower = segmento.lower()
        if any(seg_lower in s.lower() for s in segs):
            resultado.append(c)

    return resultado
