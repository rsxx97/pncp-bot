"""Agente 1 — Monitor: busca, filtra, classifica e notifica editais."""
import logging
import time
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import SCORE_MINIMO, ESTADO_FOCO
from shared.database import (
    init_db, get_db, upsert_edital, get_edital,
    set_monitor_state, registrar_execucao
)
from shared.models import EditalResumo
from agente1_monitor.pncp_client import buscar_editais, buscar_editais_nacional
from agente1_monitor.classifier import pre_filtro, classificar

log = logging.getLogger("agente1_monitor")


def edital_to_db_dict(edital: EditalResumo, score: int = None, empresa: str = None, status: str = "novo") -> dict:
    """Converte EditalResumo para dict do banco."""
    d = {
        "pncp_id": edital.pncp_id,
        "orgao_cnpj": edital.orgao_cnpj,
        "orgao_nome": edital.orgao_nome,
        "objeto": edital.objeto,
        "valor_estimado": edital.valor_estimado,
        "data_publicacao": edital.data_publicacao,
        "data_abertura": edital.data_abertura,
        "data_encerramento": edital.data_encerramento,
        "modalidade": edital.modalidade,
        "modalidade_cod": edital.modalidade_cod,
        "link_edital": edital.link_edital,
        "uf": edital.uf,
        "municipio": edital.municipio,
        "fonte": edital.fonte,
        "status": status,
    }
    if score is not None:
        d["score_relevancia"] = score
    if empresa:
        d["empresa_sugerida"] = empresa
    return d


def executar_monitor(
    usar_llm: bool = False,
    dias_retroativos: int = 3,
    modalidades: list[int] = None,
    incluir_nacional: bool = False,
) -> dict:
    """Executa um ciclo completo de monitoramento.

    Returns:
        dict com estatísticas: {"total", "novos", "relevantes", "arquivados", "duracao"}
    """
    start = time.time()
    init_db()

    stats = {
        "total_api": 0,
        "ja_conhecidos": 0,
        "novos": 0,
        "relevantes": 0,
        "arquivados": 0,
        "erros": 0,
        "duracao": 0,
    }

    if modalidades is None:
        modalidades = [4, 5, 6, 7]

    # 1. Busca local (estado foco)
    log.info(f"Buscando editais {ESTADO_FOCO} (últimos {dias_retroativos} dias)...")
    try:
        editais_local = buscar_editais(
            modalidades=modalidades,
            dias_retroativos=dias_retroativos,
        )
        stats["total_api"] += len(editais_local)
    except Exception as e:
        log.error(f"Erro na busca local: {e}")
        editais_local = []
        stats["erros"] += 1

    # 2. Busca nacional (opcional)
    editais_nacional = []
    if incluir_nacional:
        log.info("Buscando editais nacionais (>R$ 30M)...")
        try:
            editais_nacional = buscar_editais_nacional(
                modalidades=[5, 6],
                dias_retroativos=dias_retroativos,
            )
            stats["total_api"] += len(editais_nacional)
        except Exception as e:
            log.error(f"Erro na busca nacional: {e}")
            stats["erros"] += 1

    # Combina e dedup
    todos = editais_local + editais_nacional
    pncp_ids_vistos = set()
    editais_unicos = []
    for ed in todos:
        if ed.pncp_id not in pncp_ids_vistos:
            pncp_ids_vistos.add(ed.pncp_id)
            editais_unicos.append(ed)

    log.info(f"Total da API: {stats['total_api']} | Únicos: {len(editais_unicos)}")

    # 3. Filtra e classifica
    novos_relevantes = []

    for edital in editais_unicos:
        # Verifica se já existe no banco — se já existe, NÃO reprocessa nem renotifica
        existente = get_edital(edital.pncp_id)
        if existente:
            stats["ja_conhecidos"] += 1
            continue  # Pula completamente — evita renotificação no Telegram

        stats["novos"] += 1

        # Pre-filtro por keywords (nacional já veio filtrado)
        if edital.uf == ESTADO_FOCO and not pre_filtro(edital):
            # Salva como arquivado (não relevante)
            db_dict = edital_to_db_dict(edital, score=0, status="arquivado")
            upsert_edital(db_dict)
            stats["arquivados"] += 1
            continue

        # Classifica
        try:
            classificacao = classificar(edital, usar_llm=usar_llm)
        except Exception as e:
            log.error(f"Erro ao classificar {edital.pncp_id}: {e}")
            stats["erros"] += 1
            continue

        # Decide status baseado no score
        if classificacao.score >= SCORE_MINIMO:
            status = "novo"
            stats["relevantes"] += 1
            novos_relevantes.append((edital, classificacao))
            log.info(
                f"  [RELEVANTE] Score {classificacao.score}: {edital.objeto[:80]}"
            )
        else:
            status = "arquivado"
            stats["arquivados"] += 1

        # Salva no banco
        db_dict = edital_to_db_dict(
            edital,
            score=classificacao.score,
            empresa=classificacao.empresa_sugerida,
            status=status,
        )
        db_dict["justificativa_score"] = classificacao.justificativa
        db_dict["enviado_telegram"] = 1  # Marca como notificado para evitar reenvio
        upsert_edital(db_dict)

    # Atualiza estado do monitor
    duracao = time.time() - start
    stats["duracao"] = round(duracao, 1)

    set_monitor_state(
        ultima_consulta=datetime.now().isoformat(),
        total_editais_processados=stats["total_api"],
    )

    registrar_execucao(
        agente="monitor",
        pncp_id=None,
        status="sucesso" if stats["erros"] == 0 else "parcial",
        duracao_seg=duracao,
    )

    log.info(
        f"Monitor concluído em {duracao:.1f}s: "
        f"{stats['novos']} novos, {stats['relevantes']} relevantes, "
        f"{stats['arquivados']} arquivados, {stats['erros']} erros"
    )

    return {"stats": stats, "relevantes": novos_relevantes}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    result = executar_monitor(usar_llm=False, dias_retroativos=3)
    stats = result["stats"]
    print(f"\nResumo: {stats}")
    print(f"\nRelevantes ({len(result['relevantes'])}):")
    for ed, cl in result["relevantes"]:
        print(f"  [{cl.score}] {cl.empresa_sugerida} | {ed.objeto[:80]}")
