"""Extrator de tabelas estruturadas de PDFs de editais.

Extrai automaticamente postos de trabalho, quantidades, jornadas
e outros dados tabulares sem usar LLM (100% gratuito).
"""
import logging
import re
from pathlib import Path

import pdfplumber

log = logging.getLogger("table_extractor")

# Padrões para identificar tabelas de postos de trabalho
HEADERS_POSTOS = [
    "categoria profissional", "função", "cargo", "posto",
    "cbo", "descrição", "descricao",
]
HEADERS_QTD = ["quantidade", "qtd", "quant", "nº postos", "postos"]
HEADERS_JORNADA = ["carga horária", "jornada", "horas"]
HEADERS_ESCOLARIDADE = ["qualificação", "escolaridade", "grau de instrução", "formação"]


def _normalizar(texto: str) -> str:
    """Remove acentos, quebras de linha e normaliza."""
    if not texto:
        return ""
    return re.sub(r'\s+', ' ', texto.strip().lower())


def _is_header_postos(row: list) -> bool:
    """Verifica se a linha é um header de tabela de postos.

    A linha precisa ter pelo menos uma coluna de função/cargo
    E uma coluna de quantidade. Ignora linhas com merge cells
    (ex: "POSTOS DE TRABALHO" sozinho numa linha).
    """
    # Conta células não-vazias
    celulas_preenchidas = sum(1 for c in row if c and str(c).strip())
    if celulas_preenchidas < 3:
        return False  # Linha com merge, não é header real

    row_text = _normalizar(" ".join(str(c) for c in row if c))
    matches = sum(1 for h in HEADERS_POSTOS if h in row_text)
    has_qtd = any(h in row_text for h in HEADERS_QTD)
    return matches >= 1 and has_qtd


def _is_numero_puro(texto: str) -> bool:
    """Verifica se o texto é apenas um número (metragem, valor, etc).

    APRENDIZADO: Tabelas de editais frequentemente contêm metragens (m²),
    valores monetários e quantitativos que NÃO são postos de trabalho.
    Ex: "1800", "800", "300", "450.00", "R$ 5.000,00"
    Estes NUNCA devem ser confundidos com nomes de cargos/funções.
    """
    if not texto:
        return True
    s = texto.strip()
    # Remove formatação monetária e numérica
    s_clean = re.sub(r'[R$\s.,\-/()m²%]', '', s)
    # Se sobrou só dígitos, é número puro
    if s_clean.isdigit():
        return True
    # Se é muito curto e tem dígitos, provavelmente é código/número
    if len(s) <= 4 and any(c.isdigit() for c in s):
        return True
    return False


def _is_funcao_valida(funcao: str) -> bool:
    """Verifica se o texto parece ser um nome de cargo/função real.

    APRENDIZADO: Funções/cargos válidos SEMPRE contêm letras e geralmente
    são palavras reconhecíveis. Números puros, códigos, metragens e
    valores monetários NÃO são funções.
    """
    if not funcao or len(funcao.strip()) < 3:
        return False
    s = funcao.strip()

    # Rejeita se é número puro
    if _is_numero_puro(s):
        return False

    # Deve conter pelo menos 2 letras consecutivas
    if not re.search(r'[a-zA-ZáàâãéèêíïóôõúüçÁÀÂÃÉÈÊÍÏÓÔÕÚÜÇ]{2,}', s):
        return False

    # Rejeita termos que são claramente NÃO funções
    rejeitar = [
        'total', 'subtotal', 'soma', 'valor', 'preço', 'preco',
        'referência', 'referencia', 'estimado', 'mensal', 'anual',
        'item', 'lote', 'grupo', 'unidade', 'área', 'area',
        'm²', 'm2', 'metro', 'metragem', 'quantidade total',
        'observação', 'observacao', 'nota', 'obs:',
    ]
    s_lower = s.lower()
    for r in rejeitar:
        if s_lower == r or s_lower.startswith(r + ' '):
            return False

    return True


def _parse_quantidade(val) -> int | None:
    """Extrai número inteiro de uma célula."""
    if val is None:
        return None
    s = str(val).strip()
    # Extrai primeiro número encontrado
    m = re.search(r'(\d+)', s)
    if not m:
        return None
    qtd = int(m.group(1))
    # APRENDIZADO: Quantidades de postos raramente passam de 500
    # Números muito grandes são metragem/valores, não quantidade de pessoal
    if qtd > 500:
        return None
    return qtd


def _parse_jornada(val) -> str | None:
    """Extrai jornada de uma célula."""
    if val is None:
        return None
    s = str(val).lower()
    if '12x36' in s or '12 x 36' in s:
        return '12x36'
    m = re.search(r'(\d+)\s*h', s)
    if m:
        horas = int(m.group(1))
        if horas <= 36:
            return '36h'
        elif horas <= 40:
            return '40h'
        else:
            return '44h'
    return None


def _parse_escolaridade(val) -> str | None:
    """Extrai nível de escolaridade."""
    if val is None:
        return None
    s = str(val).lower()
    if 'superior' in s or 'graduação' in s:
        return 'superior'
    if 'técnico' in s or 'tecnico' in s:
        return 'tecnico'
    if 'médio' in s or 'medio' in s:
        return 'medio'
    if 'fundamental' in s:
        return 'fundamental'
    return None


def _normalizar_funcao(funcao: str) -> str:
    """Normaliza nome da função para snake_case."""
    mapa = {
        'copeiro': 'copeira',
        'copeira': 'copeira',
        'copeiragem': 'copeira',
        'recepcionista': 'recepcionista',
        'recepção': 'recepcionista',
        'porteiro': 'porteiro',
        'portaria': 'porteiro',
        'vigilante': 'vigilante',
        'vigia': 'vigilante',
        'supervisor administrativo': 'supervisor_administrativo',
        'supervisor adm': 'supervisor_administrativo',
        'secretário': 'secretario_diretoria',
        'secretária': 'secretario_diretoria',
        'secretário de diretoria': 'secretario_diretoria',
        'secretário(a) de diretoria': 'secretario_diretoria',
        'ajudante de manutenção': 'auxiliar_manutencao',
        'ajudante de manutenção predial': 'auxiliar_manutencao',
        'ajudante de manutenção de predial': 'auxiliar_manutencao',
        'auxiliar de manutenção': 'auxiliar_manutencao',
        'garçom': 'garcom',
        'garcon': 'garcom',
        'supervisor de copa': 'supervisor_copa',
        'servente': 'servente_limpeza',
        'servente de limpeza': 'servente_limpeza',
        'líder de limpeza': 'lider_limpeza',
        'encarregado': 'encarregado_limpeza',
        'encarregado de limpeza': 'encarregado_limpeza',
        'motorista': 'motorista',
        'ascensorista': 'ascensorista',
        'zelador': 'zelador',
        'jardineiro': 'jardineiro',
        'auxiliar administrativo': 'auxiliar_administrativo',
        'auxiliar de serviços gerais': 'auxiliar_servicos_gerais',
        'office boy': 'office_boy',
        'bombeiro civil': 'bombeiro_civil',
        'técnico administrativo': 'tecnico_administrativo',
    }
    funcao_lower = funcao.lower().strip()
    for chave, valor in mapa.items():
        if chave in funcao_lower:
            return valor
    # Se não encontrou, gera snake_case
    return re.sub(r'[^a-z0-9]+', '_', funcao_lower).strip('_')


def extrair_postos_tabela(pdf_path: Path | str) -> list[dict]:
    """Extrai postos de trabalho das tabelas do PDF.

    Retorna lista de dicts com:
    - funcao: str (snake_case)
    - funcao_display: str (nome original)
    - quantidade: int
    - jornada: str (44h, 40h, 36h, 12x36)
    - escolaridade: str
    - cbo: str
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return []

    postos = []
    last_header = None  # Guarda header da última tabela de postos encontrada
    last_col_map = None  # Guarda mapeamento de colunas

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    if len(table) < 2:
                        continue

                    # Procura header de postos
                    header_idx = None
                    for i, row in enumerate(table):
                        if _is_header_postos(row):
                            header_idx = i
                            break

                    # Se não achou header mas temos um da tabela anterior,
                    # pode ser continuação (mesma estrutura de colunas)
                    if header_idx is None and last_col_map is not None:
                        # Verifica se primeira linha parece dados de posto
                        first_row = table[0]
                        if len(first_row) >= len(last_header):
                            # Tenta parsear como dados usando o último mapeamento
                            funcao_col = last_col_map.get("funcao")
                            qtd_col = last_col_map.get("qtd")
                            if funcao_col is not None and qtd_col is not None:
                                funcao_raw = str(first_row[funcao_col] or "").strip()
                                qtd = _parse_quantidade(first_row[qtd_col]) if qtd_col < len(first_row) else None
                                if _is_funcao_valida(funcao_raw) and qtd and qtd > 0:
                                    # É continuação — processa com header anterior
                                    header_idx = -1  # Flag especial
                                    header = last_header

                    if header_idx is None:
                        continue

                    if header_idx >= 0:
                        header = [_normalizar(str(c)) for c in table[header_idx]]
                        log.info(f"Tabela de postos encontrada na pág {page_num}: {header}")
                    else:
                        log.info(f"Continuação da tabela de postos na pág {page_num}")

                    # Mapear colunas
                    col_funcao = None
                    col_qtd = None
                    col_jornada = None
                    col_escolaridade = None
                    col_cbo = None

                    for j, h in enumerate(header):
                        if any(k in h for k in HEADERS_POSTOS) and col_funcao is None:
                            if 'cbo' in h:
                                col_cbo = j
                            else:
                                col_funcao = j
                        if any(k in h for k in HEADERS_QTD) and col_qtd is None:
                            col_qtd = j
                        if any(k in h for k in HEADERS_JORNADA) and col_jornada is None:
                            col_jornada = j
                        if any(k in h for k in HEADERS_ESCOLARIDADE) and col_escolaridade is None:
                            col_escolaridade = j
                        if 'cbo' in h and col_cbo is None:
                            col_cbo = j

                    if col_funcao is None:
                        # Tenta CBO como fallback para identificar a coluna de função
                        if col_cbo is not None:
                            # A coluna seguinte ao CBO geralmente é a função
                            col_funcao = col_cbo + 1 if col_cbo + 1 < len(header) else None

                    if col_funcao is None or col_qtd is None:
                        continue

                    # Salvar mapeamento para detectar tabelas continuação
                    last_header = header
                    last_col_map = {
                        "funcao": col_funcao, "qtd": col_qtd,
                        "jornada": col_jornada, "escolaridade": col_escolaridade,
                        "cbo": col_cbo,
                    }

                    # Extrair dados (início depende se é header real ou continuação)
                    start_idx = header_idx + 1 if header_idx >= 0 else 0
                    for row in table[start_idx:]:
                        if len(row) <= max(col_funcao, col_qtd):
                            continue

                        funcao_raw = str(row[col_funcao] or "").strip()
                        # Limpa quebras de linha
                        funcao_raw = re.sub(r'\s+', ' ', funcao_raw)

                        # VALIDAÇÃO: rejeita números puros, metragens, valores
                        if not _is_funcao_valida(funcao_raw):
                            log.debug(f"  Rejeitado (não é função): '{funcao_raw}'")
                            continue

                        qtd = _parse_quantidade(row[col_qtd]) if col_qtd < len(row) else None
                        if qtd is None or qtd <= 0:
                            continue

                        jornada = None
                        if col_jornada is not None and col_jornada < len(row):
                            jornada = _parse_jornada(row[col_jornada])

                        escolaridade = None
                        if col_escolaridade is not None and col_escolaridade < len(row):
                            escolaridade = _parse_escolaridade(row[col_escolaridade])

                        cbo = None
                        if col_cbo is not None and col_cbo < len(row):
                            cbo_raw = str(row[col_cbo] or "").strip()
                            m = re.search(r'(\d{4}[- ]?\d{2})', cbo_raw)
                            if m:
                                cbo = m.group(1)

                        posto = {
                            "funcao": _normalizar_funcao(funcao_raw),
                            "funcao_display": funcao_raw.title(),
                            "quantidade": qtd,
                            "jornada": jornada or "44h",
                            "escolaridade_minima": escolaridade,
                            "cbo": cbo,
                        }
                        postos.append(posto)
                        log.info(f"  Posto: {posto['funcao_display']} x{qtd} | {jornada} | {escolaridade}")

    except Exception as e:
        log.error(f"Erro ao extrair tabelas: {e}")

    return postos


def extrair_valor_referencia(pdf_path: Path | str) -> dict | None:
    """Extrai valor de referência e prazo das tabelas do edital principal."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:10]:  # Só primeiras 10 páginas
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    for row in table:
                        row_text = " ".join(str(c) for c in row if c).lower()
                        # Procura valor de referência
                        if 'preço' in row_text and ('referência' in row_text or 'estimado' in row_text):
                            for cell in row:
                                if cell:
                                    # Extrai valor monetário
                                    m = re.search(r'r?\$?\s*([\d.,]+)', str(cell).replace('.', '').replace(',', '.'))
                                    if m:
                                        try:
                                            valor = float(m.group(1))
                                            if valor > 1000:  # Ignora valores muito pequenos
                                                return {"valor_referencia": valor}
                                        except ValueError:
                                            pass
    except Exception as e:
        log.error(f"Erro ao extrair valor: {e}")

    return None
