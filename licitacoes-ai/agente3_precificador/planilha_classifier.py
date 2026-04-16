"""Classificador heuristico de planilhas de licitacao.

Distingue: MDO (IN 05/2017), OBRA (TCU/BDI), AQUISICAO, SERVICO_PONTUAL, DESCONHECIDO.
Zero API — usa keywords + estrutura do arquivo.
"""
import logging
import re
from pathlib import Path

log = logging.getLogger("planilha_classifier")

TIPOS = ("mdo", "obra", "aquisicao", "servico_pontual", "desconhecido")

KEYWORDS_MDO = [
    "modulo 1", "módulo 1", "modulo i", "módulo i",
    "modulo 2", "módulo 2", "modulo 6", "módulo 6",
    "remuneracao", "remuneração", "encargos sociais",
    "cct", "convencao coletiva", "convenção coletiva",
    "posto de trabalho", "posto", "salario normativo", "salário normativo",
    "vale transporte", "vale-transporte", "vale alimentacao", "vale alimentação",
    "adicional de insalubridade", "adicional de periculosidade",
    "in 05/2017", "in 05", "in 5/2017",
    "custos indiretos", "categoria profissional",
    "uniformes", "jornada",
]

KEYWORDS_OBRA = [
    "bdi", "b.d.i", "composicao de preco", "composição de preço",
    "composicao unitaria", "composição unitária",
    "cpu", "sinapi", "sicro", "orse", "sbc",
    "leis sociais", "encargos complementares",
    "servico preliminar", "serviço preliminar",
    "planilha orcamentaria", "planilha orçamentária",
    "orcamento sintetico", "orçamento sintético",
    "orcamento analitico", "orçamento analítico",
    "cronograma fisico-financeiro", "cronograma físico-financeiro",
    "memoria de calculo", "memória de cálculo",
    "desoneracao", "desoneração",
    "m2", "m²", "m3", "m³", "metro quadrado", "metro cubico",
]

KEYWORDS_AQUISICAO = [
    "descricao do produto", "descrição do produto",
    "marca", "modelo", "ncm", "catmat", "catser",
    "unitario", "unitário", "valor unitario", "valor unitário",
    "fabricante", "especificacao tecnica", "especificação técnica",
    "lote", "item do pregao", "item do pregão",
]

KEYWORDS_EXCLUSAO_MDO = [
    "sinapi", "sicro", "bdi",  # se tem isso é obra
]


def _ler_celulas(path: Path, max_celulas: int = 2000) -> list[str]:
    """Le celulas de .xlsx/.xls como lista de strings (lowercase)."""
    ext = path.suffix.lower()
    if ext not in (".xlsx", ".xls"):
        return []

    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    except Exception as e:
        log.debug(f"Falha openpyxl {path.name}: {e}")
        return []

    textos = []
    for ws in wb.worksheets:
        try:
            for row in ws.iter_rows(values_only=True):
                for v in row:
                    if v is None:
                        continue
                    s = str(v).strip().lower()
                    if s:
                        textos.append(s)
                        if len(textos) >= max_celulas:
                            wb.close()
                            return textos
        except Exception:
            continue
    wb.close()
    return textos


def extrair_features(path: Path) -> dict:
    """Extrai features estruturais da planilha."""
    textos = _ler_celulas(path)
    corpus = " | ".join(textos)

    fname = path.name.lower()
    # Nome
    nome_mdo = any(k in fname for k in ["mao_de_obra", "mdo", "terceiriza"])
    nome_obra = any(k in fname for k in ["bdi", "orcamento", "obra", "reforma", "construcao", "sinapi"])
    nome_aquis = any(k in fname for k in ["aquisicao", "produto", "material"])

    # Counts de keywords
    hits_mdo = sum(1 for k in KEYWORDS_MDO if k in corpus)
    hits_obra = sum(1 for k in KEYWORDS_OBRA if k in corpus)
    hits_aquis = sum(1 for k in KEYWORDS_AQUISICAO if k in corpus)

    # Percentuais (típico de encargos em MDO)
    pct_count = len(re.findall(r"\b\d{1,2}[,.]\d{1,2}\s*%", corpus))

    return {
        "arquivo": path.name,
        "total_celulas": len(textos),
        "nome_mdo": nome_mdo,
        "nome_obra": nome_obra,
        "nome_aquisicao": nome_aquis,
        "hits_mdo": hits_mdo,
        "hits_obra": hits_obra,
        "hits_aquisicao": hits_aquis,
        "pct_percentuais": pct_count,
    }


def classificar_planilha(path: Path) -> dict:
    """Classifica uma planilha em MDO / OBRA / AQUISICAO / SERVICO_PONTUAL / DESCONHECIDO.

    Retorna {tipo, confianca (0-1), features, motivo}.
    """
    path = Path(path)
    if not path.exists():
        return {"tipo": "desconhecido", "confianca": 0.0, "motivo": "arquivo nao encontrado"}

    f = extrair_features(path)

    # Planilha muito pequena = servico pontual (valor unico, sem modulos)
    if f["total_celulas"] < 20:
        return {"tipo": "servico_pontual", "confianca": 0.6, "features": f, "motivo": "planilha minima"}

    scores = {
        "mdo": f["hits_mdo"] * 2 + (3 if f["nome_mdo"] else 0) + min(f["pct_percentuais"] // 3, 5),
        "obra": f["hits_obra"] * 2 + (3 if f["nome_obra"] else 0),
        "aquisicao": f["hits_aquisicao"] * 2 + (3 if f["nome_aquisicao"] else 0),
    }

    # Penaliza MDO se tem muitos sinais de obra (SINAPI, BDI)
    if f["hits_obra"] >= 3:
        scores["mdo"] = max(0, scores["mdo"] - f["hits_obra"])

    tipo_top = max(scores, key=scores.get)
    score_top = scores[tipo_top]
    score_2nd = sorted(scores.values(), reverse=True)[1]

    if score_top == 0:
        return {"tipo": "desconhecido", "confianca": 0.0, "features": f,
                "scores": scores, "motivo": "sem keywords reconhecidas"}

    # Confianca = margem sobre segundo lugar
    margem = score_top - score_2nd
    confianca = min(1.0, margem / max(1, score_top))

    return {
        "tipo": tipo_top,
        "confianca": round(confianca, 2),
        "scores": scores,
        "features": f,
        "motivo": f"top={tipo_top}({score_top}) 2o={score_2nd}",
    }
