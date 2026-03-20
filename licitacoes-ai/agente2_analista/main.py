"""Agente 2 — Analista: baixa PDF, analisa edital, gera parecer Go/No-Go."""
import json
import logging
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.database import (
    get_edital, atualizar_status_edital, registrar_execucao
)
from shared.utils import derivar_esfera
from agente1_monitor.pncp_client import buscar_arquivos_compra
from agente2_analista.pdf_extractor import download_pdf, extract_smart
from agente2_analista.edital_parser import extrair_dados_estruturados
from agente2_analista.viability_checker import verificar_viabilidade

log = logging.getLogger("agente2_analista")


def analisar_edital(pncp_id: str) -> dict:
    """Pipeline completo de análise de um edital.

    1. Busca dados do edital no banco
    2. Baixa PDF do edital da API PNCP
    3. Extrai texto do PDF
    4. Analisa via LLM (extrai dados estruturados)
    5. Verifica viabilidade (regras de negócio)
    6. Atualiza banco com resultado

    Returns:
        {"parecer": str, "analise": dict, "viabilidade": dict}
    """
    start = time.time()

    # 1. Busca edital no banco
    edital = get_edital(pncp_id)
    if not edital:
        raise ValueError(f"Edital {pncp_id} não encontrado no banco")

    atualizar_status_edital(pncp_id, "analisando")
    log.info(f"Analisando edital {pncp_id}: {edital['objeto'][:80]}")

    # 2. Busca e baixa PDF
    parts = pncp_id.split("-")
    if len(parts) >= 3:
        cnpj, ano, seq = parts[0], parts[1], parts[2]
    else:
        raise ValueError(f"pncp_id inválido: {pncp_id}")

    pdf_text = None

    try:
        arquivos = buscar_arquivos_compra(cnpj, int(ano), int(seq))
        pdf_url = None
        for arq in arquivos:
            url = arq.get("url", "")
            titulo = (arq.get("titulo", "") or "").lower()
            if url.endswith(".pdf") or "edital" in titulo:
                pdf_url = url
                break

        if pdf_url:
            filename = f"{pncp_id}.pdf"
            pdf_path = download_pdf(pdf_url, filename)
            # 3. Extrai texto
            result = extract_smart(pdf_path)
            pdf_text = result["text"]
            log.info(f"PDF: {result['pages']} páginas, {len(pdf_text)} chars extraídos")
        else:
            log.warning(f"Nenhum PDF encontrado para {pncp_id}")
    except Exception as e:
        log.warning(f"Erro ao baixar/extrair PDF: {e}")

    # Se não tem PDF, analisa só com os dados básicos
    if not pdf_text:
        pdf_text = f"""EDITAL (dados da API PNCP — sem PDF disponível):
Órgão: {edital.get('orgao_nome', 'N/I')}
Objeto: {edital.get('objeto', 'N/I')}
Valor estimado: R$ {edital.get('valor_estimado', 'N/I')}
UF: {edital.get('uf', 'N/I')}
Modalidade: {edital.get('modalidade', 'N/I')}
Data abertura: {edital.get('data_abertura', 'N/I')}"""

    # 4. Análise via LLM
    try:
        analise_dados = extrair_dados_estruturados(pdf_text, pncp_id)
    except Exception as e:
        log.error(f"Erro na análise LLM: {e}")
        analise_dados = {
            "objeto_detalhado": edital.get("objeto", ""),
            "postos_trabalho": [],
            "habilitacao": {},
            "riscos_identificados": [f"Erro na análise: {str(e)}"],
            "oportunidades": [],
        }

    # 5. Verificação de viabilidade
    empresa = edital.get("empresa_sugerida", "manutec")
    esfera = derivar_esfera(cnpj)
    atestados_exigidos = analise_dados.get("habilitacao", {}).get("qualificacao_tecnica", [])

    viabilidade = verificar_viabilidade(
        empresa_nome=empresa,
        uf_edital=edital.get("uf", ""),
        esfera=esfera,
        data_abertura=edital.get("data_abertura"),
        atestados_exigidos=atestados_exigidos,
    )

    parecer = viabilidade["parecer"]

    # 6. Atualiza banco
    analise_json = json.dumps(analise_dados, ensure_ascii=False)
    requisitos_json = json.dumps(
        analise_dados.get("habilitacao", {}), ensure_ascii=False
    )

    atualizar_status_edital(
        pncp_id,
        status=parecer,
        analise_json=analise_json,
        parecer=parecer,
        motivo_nogo=viabilidade.get("motivo_nogo"),
        requisitos_habilitacao=requisitos_json,
    )

    duracao = time.time() - start
    registrar_execucao(
        agente="analista",
        pncp_id=pncp_id,
        status="sucesso",
        duracao_seg=duracao,
    )

    log.info(f"Análise concluída: {parecer.upper()} ({duracao:.1f}s)")

    return {
        "parecer": parecer,
        "analise": analise_dados,
        "viabilidade": viabilidade,
    }


if __name__ == "__main__":
    import sys as _sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if len(_sys.argv) < 2:
        print("Uso: python -m agente2_analista.main <pncp_id>")
        print("Ex:  python -m agente2_analista.main 42498733000148-2026-442")
        _sys.exit(1)

    result = analisar_edital(_sys.argv[1])
    print(f"\nParecer: {result['parecer']}")
    print(json.dumps(result["analise"], indent=2, ensure_ascii=False)[:2000])
