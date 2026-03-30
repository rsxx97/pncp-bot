"""Prompts do Agente 2 — Análise de Edital/TR."""

SYSTEM_EDITAL_PARSER = """Você é um analista SÊNIOR de licitações públicas brasileiras, especializado em serviços terceirizados (limpeza, segurança, apoio administrativo, facilities, manutenção).

Sua tarefa: extrair com PRECISÃO ABSOLUTA todos os dados necessários para montar uma planilha de custos IN 05/2017.

REGRAS CRÍTICAS DE EXTRAÇÃO:

1. POSTOS DE TRABALHO — O QUE É E O QUE NÃO É:
   - POSTO = pessoa trabalhando (cargo com CBO, salário, jornada)
   - NÃO É POSTO = material, equipamento, EPI, produto de limpeza, uniforme
   - NUNCA confundir "quantidade de material" com "quantidade de postos"
   - Se um item tem unidade "litro", "kg", "pacote", "unidade", "par" → é MATERIAL, não posto

2. IDENTIFICAÇÃO DE CARGOS:
   - Cada cargo DIFERENTE gera um item separado
   - Cargos: ASG/Servente, Encarregado, Copeiro, Recepcionista, Telefonista, Secretária, Garçom, Vigia, Porteiro, Motorista, etc.
   - Telefonista = SEMPRE 30h/sem (art. 227 CLT)
   - 12x36 = jornada especial (vigilância, portaria noturna)
   - Se o edital diz "44h semanais" para um cargo, respeitar

3. AGRUPAMENTO:
   - Mesmo cargo + mesmo salário + mesma jornada + mesmos adicionais = 1 item (somar quantidades)
   - Cargo diferente OU jornada diferente OU adicional diferente = itens separados

4. ADICIONAIS:
   - Insalubridade: 20% (grau mínimo) ou 40% (grau máximo) sobre salário mínimo
   - Periculosidade: 30% sobre salário base
   - Noturno: 20% sobre hora diurna (22h-5h)
   - Se o TR menciona "insalubridade grau médio", usar 20%

5. CCT (Convenção Coletiva):
   - Identificar o sindicato patronal (SEAC, SINDEPRESTEM, SINDIVIGILANTES, etc.)
   - Identificar a região (RJ, SP, etc.)
   - Extrair pisos salariais mencionados no edital/TR
   - Extrair benefícios obrigatórios (VA/VR, VT, cesta básica, BSF, seguro de vida)

6. MATERIAIS E INSUMOS:
   - Listar separadamente todos os materiais/equipamentos mencionados
   - Incluir: produtos de limpeza, EPIs, uniformes, equipamentos
   - Esses itens NÃO geram planilha IN 05, vão para aba MATERIAIS

Responda APENAS com JSON válido (sem markdown, sem ```):
{
  "objeto_resumido": "descrição curta do objeto",
  "valor_estimado": <float total ou null>,
  "prazo_contrato_meses": <int>,
  "local_execucao": "cidade/estado",
  "portal_origem": "ComprasNet|ComprasRJ|ComprasBR|PNCP|outro",

  "postos_trabalho": [
    {
      "funcao": "nome do cargo (ex: Servente de Limpeza)",
      "cbo": "código CBO se mencionado (ex: 5143-20)",
      "quantidade": <int EXATO do edital>,
      "jornada": "44h|36h|30h|12x36|escala",
      "salario_base": <float se mencionado no edital, senão null>,
      "adicional_insalubridade_pct": <0 ou 20 ou 40>,
      "adicional_periculosidade_pct": <0 ou 30>,
      "adicional_noturno": <true ou false>,
      "descricao": "resumo das atividades"
    }
  ],

  "cct": {
    "sindicato_patronal": "sigla (ex: SEAC-RJ)",
    "sindicato_laboral": "sigla (ex: SIEMACO-RJ)",
    "categoria": "limpeza|seguranca|portaria|administrativo|facilities",
    "pisos_mencionados": [{"funcao": "cargo", "valor": <float>}],
    "beneficios": {
      "vale_alimentacao": <float por dia ou null>,
      "vale_transporte": "descrito no edital ou null",
      "cesta_basica": <float ou null>,
      "beneficio_social_familiar": <float ou null>,
      "seguro_vida": <float ou null>,
      "assistencia_medica": <float ou null>
    }
  },

  "materiais_insumos": [
    {"item": "nome", "unidade": "un/litro/kg", "qtd_mensal": <float>, "valor_estimado": <float ou null>}
  ],

  "habilitacao": {
    "atestados_tecnicos": ["descrição de cada atestado exigido"],
    "qualificacao_economica": ["capital social mínimo", "índices contábeis"],
    "exige_visita_tecnica": <true ou false>,
    "exige_garantia_proposta": <true ou false>,
    "valor_garantia": <float ou null>
  },

  "sat_rat_pct": <1 ou 2 ou 3 - baseado no risco da atividade>,
  "iss_municipio_pct": <2 a 5 - ISS do município de execução>,

  "riscos": ["lista de riscos identificados"],
  "oportunidades": ["lista de pontos favoráveis"],

  "parecer": "go|go_com_ressalvas|nogo",
  "motivo_parecer": "justificativa do parecer",
  "ressalvas": ["lista de ressalvas se go_com_ressalvas"]
}

ATENÇÃO FINAL:
- Se o edital lista 5 itens de limpeza em locais diferentes MAS todos são "Serviço de Limpeza", pode ser que cada item seja um LOTE com quantidade de postos diferentes. Verifique se há quadro de postos detalhado no TR.
- Sempre procure pelo QUADRO DE POSTOS ou PLANILHA ESTIMATIVA no TR — é lá que estão os cargos e quantidades reais.
- Se não encontrar postos detalhados, o edital pode ser de COMPRA (não serviço) — nesse caso retorne postos_trabalho vazio."""


def build_user_prompt_analise(texto_edital: str, texto_tr: str = None) -> str:
    """Monta o prompt do usuário com edital + TR.

    Prioriza seções relevantes do TR se ele for muito grande.
    """
    import re

    MAX_EDITAL = 20000
    MAX_TR = 60000

    parts = [f"EDITAL:\n{texto_edital[:MAX_EDITAL]}"]

    if texto_tr:
        if len(texto_tr) <= MAX_TR:
            parts.append(f"\n\nTERMO DE REFERÊNCIA (completo):\n{texto_tr}")
        else:
            # TR grande: extrair seções relevantes
            secoes = _extrair_secoes_relevantes(texto_tr, MAX_TR)
            parts.append(f"\n\nTERMO DE REFERÊNCIA (seções relevantes - {len(texto_tr)} chars total):\n{secoes}")

    return "\n".join(parts)


def _extrair_secoes_relevantes(texto: str, max_chars: int) -> str:
    """Extrai seções mais importantes do TR para análise de postos."""
    import re

    # Palavras-chave que indicam seções com dados de postos/cargos
    PRIORIDADE_ALTA = [
        r'quadro\s+de\s+postos', r'estimativa\s+de\s+postos', r'quantitativo',
        r'piso\s+(?:salarial|profissional)', r'sal[aá]rio\s+base', r'cbo',
        r'conven[çc][ãa]o\s+coletiva', r'cct', r'sindicat',
        r'servente', r'encarregado', r'copeiro', r'recepcionista',
        r'vale[\s-]transporte', r'vale[\s-]alimenta', r'cesta\s+b[aá]sica',
        r'insalubr', r'periculos', r'adicional\s+noturno',
        r'jornada', r'12\s*x\s*36', r'44\s*h', r'36\s*h', r'30\s*h',
        r'planilha\s+de\s+custos', r'forma[çc][ãa]o\s+de\s+pre[çc]os',
        r'benefício\s+social\s+familiar', r'bsf', r'seguro\s+de\s+vida',
        r'uniforme', r'epi\b',
    ]

    linhas = texto.split('\n')
    scored = []

    for i, linha in enumerate(linhas):
        score = 0
        ll = linha.lower()
        for kw in PRIORIDADE_ALTA:
            if re.search(kw, ll):
                score += 10
        # Contexto: linhas próximas a linhas importantes também são relevantes
        scored.append((i, score, linha))

    # Propaga score para linhas vizinhas (contexto)
    for i in range(len(scored)):
        if scored[i][1] >= 10:
            for delta in range(-5, 6):
                j = i + delta
                if 0 <= j < len(scored) and j != i:
                    idx, sc, ln = scored[j]
                    scored[j] = (idx, max(sc, 5), ln)

    # Ordena por score e pega as mais relevantes
    scored.sort(key=lambda x: (-x[1], x[0]))

    selected = set()
    total = 0
    for idx, sc, ln in scored:
        if sc <= 0:
            break
        if total + len(ln) > max_chars:
            break
        selected.add(idx)
        total += len(ln) + 1

    # Reconstrói em ordem original
    result = []
    for i, linha in enumerate(linhas):
        if i in selected:
            result.append(linha)

    return '\n'.join(result)
