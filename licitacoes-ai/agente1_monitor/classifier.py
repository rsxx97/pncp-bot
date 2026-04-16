"""Classificador de relevância de editais — keyword + LLM scoring."""
import json
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import KEYWORDS_INTERESSE, KEYWORDS_EXCLUSAO, SCORE_MINIMO, KEYWORDS_POR_UF
from shared.models import EditalResumo, ClassificacaoEdital
from shared.utils import contem_palavra_chave, contem_exclusao, derivar_esfera, formatar_valor

log = logging.getLogger("classifier")

# ── Classificação rápida por keywords (sem LLM) ───────────────────────

def pre_filtro(edital: EditalResumo) -> bool:
    """Filtro rápido por keywords. Retorna True se o edital passa.

    Aceita se:
    1. Nicho detectado != "outros" (residuos, obra, seguranca, admin, mdo_limpeza), OU
    2. Match em KEYWORDS_INTERESSE genérico.
    Rejeita se contém KEYWORDS_EXCLUSAO ou tem keywords específicas da UF sem match.
    """
    from shared.nichos import detectar_nicho

    objeto = (edital.objeto or "").lower()

    if contem_exclusao(objeto):
        return False

    # Nicho reconhecido = aceita direto
    nicho = detectar_nicho(objeto)
    if nicho != "outros":
        return True

    # UF com lista dedicada
    kws_uf = KEYWORDS_POR_UF.get((edital.uf or "").upper())
    if kws_uf:
        return any(k in objeto for k in kws_uf)

    return contem_palavra_chave(objeto)


def score_rapido(edital: EditalResumo) -> int:
    """Calcula score básico sem LLM (heurística para triagem inicial).

    Usado quando a API Claude não está disponível ou para
    pré-ordenar editais antes de enviar ao LLM.
    """
    score = 0
    objeto = (edital.objeto or "").lower().replace("-", " ")

    # Aderência ao core business (0-40)
    keywords_limpeza = ["limpeza", "conservação", "asseio", "facilities", "predial", "zeladoria"]
    keywords_admin = ["apoio administrativo", "recepção", "portaria", "copeiragem"]
    keywords_seg = ["vigilância", "segurança", "vigia", "brigada", "bombeiro"]
    keywords_manut = ["manutenção predial", "engenharia", "construção", "reforma"]
    keywords_terceirizacao = ["terceirização", "mão de obra", "mao de obra"]

    if any(k in objeto for k in keywords_limpeza):
        score += 40
    elif any(k in objeto for k in keywords_seg):
        score += 35
    elif any(k in objeto for k in keywords_admin):
        score += 35
    elif any(k in objeto for k in keywords_terceirizacao):
        score += 30
    elif any(k in objeto for k in keywords_manut):
        score += 25
    else:
        score += 10

    # Localização (0-20)
    if edital.uf == "RJ":
        score += 20
    elif edital.uf in ("ES", "MG", "SP"):
        score += 10
    else:
        score += 5

    # Valor (0-15)
    valor = edital.valor_estimado
    if valor is not None:
        if valor >= 10_000_000:
            score += 15
        elif valor >= 1_000_000:
            score += 12
        elif valor >= 100_000:
            score += 8
        elif valor >= 10_000:
            score += 4

    # Modalidade (0-10)
    if edital.modalidade_cod == 6:  # Pregão eletrônico
        score += 10
    elif edital.modalidade_cod in (5, 7):  # Concorrência / Pregão presencial
        score += 8
    elif edital.modalidade_cod == 4:  # Concorrência Loss
        score += 6

    # Penalidade se federal + Manutec tem sanção
    esfera = derivar_esfera(edital.orgao_cnpj)
    if esfera == "federal":
        score = max(score - 10, 0)

    return min(score, 100)


def sugerir_empresa(edital: EditalResumo) -> str:
    """Sugere qual empresa do grupo deve participar (heurística)."""
    objeto = (edital.objeto or "").lower().replace("-", " ")

    keywords_miami = ["vigilância", "segurança", "vigia", "controlador de acesso", "brigada", "bombeiro"]
    keywords_blue = ["apoio administrativo", "recepção", "recepcionista", "portaria", "copeira", "copeiragem"]

    if any(k in objeto for k in keywords_miami):
        return "miami"
    if any(k in objeto for k in keywords_blue):
        return "blue"
    return "manutec"


def classificar_rapido(edital: EditalResumo) -> ClassificacaoEdital:
    """Classificação completa sem LLM (heurística)."""
    score = score_rapido(edital)
    empresa = sugerir_empresa(edital)
    esfera = derivar_esfera(edital.orgao_cnpj)

    tags = [edital.uf.lower() if edital.uf else "?"]
    if esfera != "desconhecida":
        tags.append(esfera)

    alertas = []
    if esfera == "federal" and empresa == "manutec":
        alertas.append("Manutec tem sanção AGU ativa até jun/2026 — considerar Blue ou Miami")

    return ClassificacaoEdital(
        pncp_id=edital.pncp_id,
        score=score,
        justificativa=f"Score heurístico. Empresa sugerida: {empresa}. UF: {edital.uf}. Valor: {formatar_valor(edital.valor_estimado)}",
        empresa_sugerida=empresa,
        tags=tags,
        alertas=alertas,
    )


# ── Classificação via LLM (Claude) ────────────────────────────────────

SYSTEM_PROMPT = """Você é um analista de licitações públicas especializado em serviços
terceirizados no Rio de Janeiro. Avalie o edital abaixo e atribua um
score de 0 a 100 baseado na relevância para o grupo de empresas.

EMPRESAS DO GRUPO:
- Manutec: limpeza, conservação, facilities, mão de obra terceirizada
  CNAEs: 8121-4/00, 8111-7/00, 8130-3/00, 7810-8/00
- Blue Soluções: apoio administrativo, recepção, portaria, copeiragem
  CNAEs: 8211-3/00, 7810-8/00
- Miami Segurança: vigilância, segurança patrimonial, brigada de incêndio
  CNAEs: 8012-9/00, 8011-1/01

RESTRIÇÃO ATIVA: Manutec possui sanção AGU (nacional) ativa até jun/2026.
Editais FEDERAIS devem ter score reduzido em 30 pontos para Manutec.
Blue e Miami NÃO possuem sanções.

CRITÉRIOS DE SCORING:
- Aderência ao core business (0-40 pontos)
- Localização compatível - RJ é ideal, RJ+adjacentes ok (0-20 pontos)
- Valor estimado atrativo - R$1M+ preferível (0-15 pontos)
- Prazo de contrato - 12+ meses preferível (0-10 pontos)
- Complexidade de habilitação - quanto mais simples, melhor (0-15 pontos)

Responda APENAS com JSON válido:
{
  "score": <int 0-100>,
  "justificativa": "<2-3 frases>",
  "empresa_sugerida": "<manutec|blue|miami>",
  "tags": ["<tag1>", "<tag2>"],
  "alertas": ["<alerta se houver>"]
}"""


def _build_user_prompt(edital: EditalResumo) -> str:
    esfera = derivar_esfera(edital.orgao_cnpj)
    return f"""EDITAL:
- Órgão: {edital.orgao_nome}
- CNPJ Órgão: {edital.orgao_cnpj}
- Objeto: {edital.objeto}
- Valor estimado: {formatar_valor(edital.valor_estimado)}
- UF: {edital.uf} / Município: {edital.municipio or 'N/I'}
- Data abertura: {edital.data_abertura or 'N/I'}
- Modalidade: {edital.modalidade or 'N/I'}
- Esfera: {esfera}"""


def classificar_llm(edital: EditalResumo) -> ClassificacaoEdital:
    """Classificação via Claude API (mais precisa, usa tokens)."""
    from shared.llm_client import ask_claude_json

    user_prompt = _build_user_prompt(edital)

    try:
        result = ask_claude_json(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=512,
            agente="monitor_classifier",
            pncp_id=edital.pncp_id,
        )

        return ClassificacaoEdital(
            pncp_id=edital.pncp_id,
            score=result.get("score", 0),
            justificativa=result.get("justificativa", ""),
            empresa_sugerida=result.get("empresa_sugerida", "manutec"),
            tags=result.get("tags", []),
            alertas=result.get("alertas", []),
        )

    except Exception as e:
        log.error(f"Erro na classificação LLM para {edital.pncp_id}: {e}")
        # Fallback para classificação rápida
        return classificar_rapido(edital)


def classificar(edital: EditalResumo, usar_llm: bool = False) -> ClassificacaoEdital:
    """Classifica edital. Usa LLM se configurado, senão heurística."""
    if usar_llm:
        return classificar_llm(edital)
    return classificar_rapido(edital)
