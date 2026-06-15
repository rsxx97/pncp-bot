"""Parsing estruturado de editais — 100% código puro (regex + pdfplumber).

Zero dependência de API externa. Extrai:
- objeto, valor estimado, prazo
- postos de trabalho (função, quantidade, jornada)
- CCT (sindicato, salário)
- habilitação (documentos exigidos)
- parecer heurístico (viabilidade)
"""
import logging
import re

log = logging.getLogger("edital_parser")

# ══════════════════════════════════════════════════════════════
# REGEX DE EXTRAÇÃO
# ══════════════════════════════════════════════════════════════

# Valor estimado
VALOR_REGEX = [
    re.compile(r"valor\s+(?:total\s+)?estimado[:\s]+R?\$?\s*([\d\.\,]+)", re.IGNORECASE),
    re.compile(r"valor\s+m[áa]ximo[:\s]+R?\$?\s*([\d\.\,]+)", re.IGNORECASE),
    re.compile(r"valor\s+global[:\s]+R?\$?\s*([\d\.\,]+)", re.IGNORECASE),
    re.compile(r"R\$\s*([\d\.\,]+)\s*\(.*?(?:reais|total|estimado)", re.IGNORECASE),
]

# Prazo
PRAZO_REGEX = [
    re.compile(r"prazo\s+(?:de\s+)?(?:vig[êe]ncia|execu[çc][ãa]o|contrato)[:\s]+(\d+)\s*(mes|meses|ano|anos|dia|dias)", re.IGNORECASE),
    re.compile(r"(\d+)\s*\((?:doze|vinte e quatro|trinta e seis)\)\s*meses", re.IGNORECASE),
]

# CCT / Sindicato
CCT_REGEX = [
    re.compile(r"(SIEMACO[\-\s]?[A-Z]+|SINDESV[\-\s]?[A-Z]+|SEAC[\-\s]?[A-Z]+|SINTEIC[\-\s]?[A-Z]+|SENGE[\-\s]?[A-Z]+|SINTRASCOM[\-\s]?[A-Z]+|SINDLIMP[\-\s]?[A-Z]+)", re.IGNORECASE),
    re.compile(r"conven[çc][ãa]o\s+coletiva[^\n]*?(\d{4}/\d{4})", re.IGNORECASE),
    re.compile(r"CCT\s+(\d{4}/\d{4})", re.IGNORECASE),
]

# Piso salarial
SALARIO_REGEX = [
    re.compile(r"(?:piso|sal[áa]rio)\s+(?:base|salarial)?[:\s]+R?\$?\s*([\d\.\,]+)", re.IGNORECASE),
    re.compile(r"sal[áa]rio\s+mensal[:\s]+R?\$?\s*([\d\.\,]+)", re.IGNORECASE),
]

# Postos de trabalho (função + quantidade)
POSTO_KEYWORDS = [
    # Segurança
    (r"vigilante\s+armado", "Vigilante Armado"),
    (r"vigilante\s+desarmado", "Vigilante Desarmado"),
    (r"vigia", "Vigia"),
    (r"porteiro", "Porteiro"),
    (r"bombeiro\s+(?:civil|profissional)", "Bombeiro Civil"),
    (r"controlador\s+de\s+acesso", "Controlador de Acesso"),
    # Limpeza
    (r"servente\s+(?:de\s+limpeza)?", "Servente de Limpeza"),
    (r"auxiliar\s+de\s+limpeza", "Auxiliar de Limpeza"),
    (r"encarregado\s+(?:de\s+limpeza|geral)", "Encarregado Geral"),
    # Admin
    (r"recepcionist[ao]", "Recepcionista"),
    (r"telefonist[ao]", "Telefonista"),
    (r"secret[áa]ri[ao]", "Secretário(a)"),
    (r"auxiliar\s+administrativo", "Auxiliar Administrativo"),
    # Copeiragem
    (r"copeir[ao]", "Copeiro(a)"),
    (r"gar[çc]om", "Garçom"),
    (r"cozinheir[ao]", "Cozinheiro(a)"),
    # Motorista
    (r"motorist[ao]", "Motorista"),
    # ASG
    (r"auxiliar\s+de\s+servi[çc]os\s+gerais", "ASG"),
    (r"\bASG\b", "ASG"),
    # Resíduos
    (r"gari", "Gari"),
    (r"coletor\s+(?:de\s+lixo)?", "Coletor"),
    (r"varredor", "Varredor"),
    # Manutenção predial
    (r"eletricista", "Eletricista"),
    (r"encanador", "Encanador"),
    (r"bombeiro\s+hidr[áa]ulico", "Bombeiro Hidráulico"),
    (r"pintor\s+predial", "Pintor Predial"),
    (r"serralheiro", "Serralheiro"),
    # Jardinagem
    (r"jardineiro", "Jardineiro"),
    # Brigada
    (r"brigadista", "Brigadista"),
]

# Jornada
JORNADA_REGEX = re.compile(r"(12x36|44h|40h|30h|20h|220h|8h\s*di[áa]ri[ao]s)", re.IGNORECASE)
TELEFONISTA_JORNADA = "30h"  # CLT art 227

# Habilitação (documentos exigidos nos editais)
HABILITACAO_DOCS = [
    # Jurídica
    "ato constitutivo",
    "contrato social",
    "registro comercial",
    "cart[ãa]o CNPJ",
    "cart[ãa]o de CPF",
    "inscri[çc][ãa]o estadual",
    "inscri[çc][ãa]o municipal",
    "alvar[áa] de funcionamento",
    # Fiscal e Trabalhista
    "certid[ãa]o negativa de d[ée]bitos",
    "certid[ãa]o de reg[ui]laridade fiscal",
    "CND Federal",
    "CND Estadual",
    "CND Municipal",
    "CNDT",
    "Certid[ãa]o Negativa de D[ée]bitos Trabalhistas",
    "CRF",
    "CRF FGTS",
    "Certificado de Regularidade do FGTS",
    "FGTS",
    "INSS",
    # Econômico-Financeira
    "balan[çc]o patrimonial",
    "demonstra[çc][ãa]o (?:cont[áa]bil|do resultado)",
    "[íi]ndices? (?:econ[ôo]mico[\\-\\s]financeiro|de liquidez)",
    "liquidez corrente",
    "liquidez geral",
    "solv[êe]ncia geral",
    "endividamento",
    "capital (?:social|circulante)\\s+m[íi]nimo",
    "patrim[ôo]nio l[íi]quido",
    "certid[ãa]o negativa de fal[êe]ncia",
    "certid[ãa]o de recupera[çc][ãa]o judicial",
    # Técnica
    "atestado de capacidade t[ée]cnica",
    "atestado de execu[çc][ãa]o",
    "CREA",
    "CAU",
    "responsabilidade t[ée]cnica",
    "acervo t[ée]cnico",
    "CAT",
    # Outros
    "pr[oó]-labore",
    "CRC",
    "declara[çc][ãa]o de menor",
    "declara[çc][ãa]o de inexist[êe]ncia",
    "declara[çc][ãa]o de elabora[çc][ãa]o independente",
    "declara[çc][ãa]o de (?:micro)?empresa",
]

# Garantias / Cauções
GARANTIA_PATTERNS = {
    "seguro_garantia_proposta": re.compile(
        r"seguro[\-\s]+garantia[^.\n]*?(?:proposta|manuten[çc][ãa]o)[^.\n]{0,200}",
        re.IGNORECASE
    ),
    "garantia_contratual": re.compile(
        r"garantia\s+(?:contratual|de\s+execu[çc][ãa]o)[^.\n]{0,200}",
        re.IGNORECASE
    ),
    "caucao": re.compile(
        r"cau[çc][ãa]o[^.\n]{0,200}",
        re.IGNORECASE
    ),
}

# Percentual de garantia (ex: "5% do valor do contrato")
GARANTIA_PCT_REGEX = re.compile(
    r"(\d+(?:[,\.]\d+)?)\s*%\s*(?:do\s+)?(?:valor\s+)?(?:do\s+)?(?:contrato|proposta|estimado)",
    re.IGNORECASE
)

# Valor mínimo de atestado
ATESTADO_VALOR_REGEX = re.compile(
    r"atestado[^.\n]*?(?:valor|montante)[^.\n]*?R?\$?\s*([\d\.\,]+)",
    re.IGNORECASE
)

# Área mínima exigida (obras)
AREA_MIN_REGEX = re.compile(
    r"(\d+(?:[,\.]\d+)?)\s*m[²2]\s*(?:de\s+)?(?:[áa]rea|constru[ií]da|executada)",
    re.IGNORECASE
)

# Capital social mínimo
CAPITAL_REGEX = re.compile(
    r"capital\s+(?:social|circulante)[^.\n]*?R?\$?\s*([\d\.\,]+)",
    re.IGNORECASE
)


def _parse_valor_br(texto: str) -> float:
    """Converte '1.234.567,89' → 1234567.89 (formato brasileiro)."""
    if not texto:
        return 0.0
    texto = texto.strip().replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def _extrair_valor(texto: str) -> float:
    """Extrai valor estimado."""
    for regex in VALOR_REGEX:
        m = regex.search(texto)
        if m:
            return _parse_valor_br(m.group(1))
    return 0.0


def _extrair_prazo(texto: str) -> int:
    """Extrai prazo em meses."""
    for regex in PRAZO_REGEX:
        m = regex.search(texto)
        if m:
            num = int(m.group(1))
            unidade = (m.group(2) if m.lastindex >= 2 else "meses").lower()
            if "ano" in unidade:
                return num * 12
            if "dia" in unidade:
                return max(1, num // 30)
            return num
    return 12  # default


def _extrair_cct(texto: str) -> dict:
    """Extrai dados da CCT."""
    cct = {"sindicato_laboral": None, "sindicato_patronal": None, "vigencia": None}
    for regex in CCT_REGEX:
        m = regex.search(texto)
        if m:
            val = m.group(1).upper().strip()
            if "/" in val:
                cct["vigencia"] = val
            else:
                cct["sindicato_laboral"] = val
            break
    # Piso salarial
    for regex in SALARIO_REGEX:
        m = regex.search(texto)
        if m:
            cct["piso_salarial"] = _parse_valor_br(m.group(1))
            break
    return cct


def _extrair_postos(texto: str) -> list:
    """Extrai postos de trabalho (função + quantidade)."""
    postos = []
    texto_lower = texto.lower()

    for pattern, nome in POSTO_KEYWORDS:
        # Busca "função seguido de número" ou "número seguido de função"
        pat_num_func = re.compile(rf"(\d+)\s*(?:postos?\s+de\s+)?{pattern}", re.IGNORECASE)
        pat_func_num = re.compile(rf"{pattern}[^.\n]*?(\d+)\s*(?:posto|unidade|pessoa|profiss|postos?)", re.IGNORECASE)

        qtd = 0
        for m in pat_num_func.finditer(texto_lower):
            try:
                q = int(m.group(1))
                if 0 < q < 1000:
                    qtd = max(qtd, q)
            except ValueError:
                pass
        for m in pat_func_num.finditer(texto_lower):
            try:
                q = int(m.group(1))
                if 0 < q < 1000:
                    qtd = max(qtd, q)
            except ValueError:
                pass

        # Se a função existe mas não detectou quantidade, assume 1
        if qtd == 0 and re.search(pattern, texto_lower):
            qtd = 1

        if qtd > 0:
            # Detecta jornada no contexto próximo
            jornada = "44h"
            contexto_idx = texto_lower.find(re.search(pattern, texto_lower).group(0)) if re.search(pattern, texto_lower) else -1
            if contexto_idx > 0:
                contexto = texto[contexto_idx:contexto_idx + 300]
                m_jornada = JORNADA_REGEX.search(contexto)
                if m_jornada:
                    jornada = m_jornada.group(1).lower().replace(" ", "")

            # Telefonista sempre 30h (CLT art 227)
            if "telefonist" in nome.lower():
                jornada = TELEFONISTA_JORNADA

            postos.append({
                "funcao": nome,
                "quantidade": qtd,
                "jornada": jornada,
                "descricao": nome,
            })

    return postos


def _extrair_habilitacao(texto: str) -> list:
    """Extrai documentos de habilitação exigidos."""
    docs_encontrados = []
    for doc_pattern in HABILITACAO_DOCS:
        if re.search(doc_pattern, texto, re.IGNORECASE):
            docs_encontrados.append(re.search(doc_pattern, texto, re.IGNORECASE).group(0))
    return list(set(d.title() for d in docs_encontrados))


def _extrair_garantias(texto: str, valor_estimado: float) -> dict:
    """Extrai exigências de garantia (seguro garantia, caução, garantia contratual)."""
    garantias = {
        "tem_seguro_garantia_proposta": False,
        "tem_garantia_contratual": False,
        "percentual_garantia": None,
        "valor_estimado_garantia": None,
        "trechos": [],
    }

    for nome, regex in GARANTIA_PATTERNS.items():
        m = regex.search(texto)
        if m:
            trecho = m.group(0)[:200]
            garantias["trechos"].append({nome: trecho})
            if "proposta" in nome or "manuten" in trecho.lower():
                garantias["tem_seguro_garantia_proposta"] = True
            if "contratual" in nome or "execucao" in trecho.lower():
                garantias["tem_garantia_contratual"] = True

    # Busca percentual de garantia
    m = GARANTIA_PCT_REGEX.search(texto)
    if m:
        try:
            pct = float(m.group(1).replace(",", "."))
            if 0 < pct <= 20:  # garantias típicas 1-10%
                garantias["percentual_garantia"] = pct
                if valor_estimado > 0:
                    garantias["valor_estimado_garantia"] = round(valor_estimado * pct / 100, 2)
        except ValueError:
            pass

    return garantias


def _extrair_requisitos_tecnicos(texto: str) -> dict:
    """Extrai requisitos técnicos (atestados, área mínima, experiência)."""
    req = {
        "atestado_valor_minimo": None,
        "area_minima_m2": None,
        "capital_social_minimo": None,
        "anos_experiencia": None,
        "quantidade_atestados_exigidos": 0,
    }

    # Valor mínimo de atestado
    m = ATESTADO_VALOR_REGEX.search(texto)
    if m:
        req["atestado_valor_minimo"] = _parse_valor_br(m.group(1))

    # Contar quantos atestados são exigidos
    atestados_matches = re.findall(r"atestado[s]?\s+(?:de\s+)?capacidade", texto, re.IGNORECASE)
    req["quantidade_atestados_exigidos"] = len(atestados_matches)

    # Área mínima
    m = AREA_MIN_REGEX.search(texto)
    if m:
        val = m.group(1).replace(",", ".")
        try:
            req["area_minima_m2"] = float(val)
        except ValueError:
            pass

    # Capital social
    m = CAPITAL_REGEX.search(texto)
    if m:
        req["capital_social_minimo"] = _parse_valor_br(m.group(1))

    # Anos de experiência
    m = re.search(r"(\d+)\s*anos?\s+de\s+experi[êe]ncia", texto, re.IGNORECASE)
    if m:
        try:
            req["anos_experiencia"] = int(m.group(1))
        except ValueError:
            pass

    return req


def _parecer_heuristico(valor: float, postos: list, habilitacao: list) -> str:
    """Gera parecer Go/No-Go baseado em heurística."""
    if valor == 0:
        return "INCONCLUSIVO — valor não identificado"
    if valor < 10000:
        return "PULAR — valor muito baixo"
    if not postos and not habilitacao:
        return "REVISAR MANUAL — extração regex inconclusiva"
    if len(postos) > 0 and len(habilitacao) >= 3:
        return "PARTICIPAR — dados suficientes, vale analisar"
    return "REVISAR — dados parciais"


def extrair_dados_estruturados(texto_edital: str, pncp_id: str = None, texto_tr: str = None) -> dict:
    """Extrai dados estruturados do edital usando REGEX PURO (zero API).

    Args:
        texto_edital: texto do edital (PDF extraído)
        pncp_id: id do edital
        texto_tr: texto do TR (termo de referência)

    Returns:
        Dict com dados estruturados. Sempre tem _metodo="regex_puro".
    """
    texto_completo = texto_edital + ("\n" + texto_tr if texto_tr else "")
    log.info(f"Extraindo via regex puro ({len(texto_completo)} chars, zero API)...")

    valor = _extrair_valor(texto_completo)
    prazo_meses = _extrair_prazo(texto_completo)
    cct = _extrair_cct(texto_completo)
    postos = _extrair_postos(texto_completo)
    habilitacao = _extrair_habilitacao(texto_completo)
    garantias = _extrair_garantias(texto_completo, valor)
    requisitos = _extrair_requisitos_tecnicos(texto_completo)
    parecer = _parecer_heuristico(valor, postos, habilitacao)

    result = {
        "_metodo": "regex_puro",
        "_pncp_id": pncp_id,
        "valor_estimado": valor,
        "prazo_meses": prazo_meses,
        "cct": cct,
        "postos_trabalho": postos,
        "habilitacao_documentos": habilitacao,
        "garantias": garantias,
        "requisitos_tecnicos": requisitos,
        "parecer": parecer,
        "materiais_insumos": [],
    }

    # Flag para revisão manual se extração ficou pobre
    if not postos and not habilitacao:
        result["_needs_manual_review"] = True
        result["_reason"] = "regex puro não identificou postos nem habilitação"

    log.info(f"Regex: {len(postos)} postos | valor R$ {valor:,.2f} | "
             f"prazo {prazo_meses}m | {len(habilitacao)} docs | "
             f"seguro_proposta={garantias['tem_seguro_garantia_proposta']} | "
             f"atestados={requisitos['quantidade_atestados_exigidos']} | {parecer}")

    return result
