"""Agente 3 — Precificador: orquestra cálculo de custos IN 05/2017."""
import json
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_DIR
from shared.database import (
    get_edital, get_editais_pendentes, atualizar_status_edital,
    adicionar_comentario, init_db,
)
from shared.llm_client import ask_claude_json
from agente3_precificador.cct_manager import (
    get_piso_salarial, get_beneficios, importar_ccts_diretorio,
)
from agente3_precificador.encargos import calcular_posto_completo
from agente3_precificador.tributos import calcular_tributos
from agente3_precificador.bdi_simulator import simular_cenarios
from agente3_precificador.planilha_builder import gerar_planilha
from agente3_precificador.template_filler import (
    detectar_template_info, preencher_template, pode_usar_template,
)
from agente3_precificador.planilha_classifier import classificar_planilha
from agente3_precificador.prompts import (
    SYSTEM_EXTRAIR_POSTOS, PROMPT_EXTRAIR_POSTOS,
)

def _load_empresa_perfil() -> list[dict]:
    """Carrega perfil das empresas do grupo."""
    perfil_path = Path(__file__).parent.parent / "config" / "empresa_perfil.json"
    with open(perfil_path, "r", encoding="utf-8") as f:
        return json.load(f)["empresas"]


def _load_mdo_padrao() -> dict:
    """Carrega MDO padrão do grupo."""
    mdo_path = Path(__file__).parent.parent / "config" / "mdo_padrao.json"
    with open(mdo_path, "r", encoding="utf-8") as f:
        return json.load(f)


_SKILLS_CACHE = None

def _load_skills_pncp() -> dict:
    """Carrega skills absorvidos de planilhas reais de licitações ganhas."""
    global _SKILLS_CACHE
    if _SKILLS_CACHE is not None:
        return _SKILLS_CACHE
    skills_path = Path(__file__).parent.parent / "bot_pncp_skills" / "data" / "skills" / "skills_consolidado.json"
    if not skills_path.exists():
        _SKILLS_CACHE = {}
        return _SKILLS_CACHE
    try:
        with open(skills_path, "r", encoding="utf-8") as f:
            _SKILLS_CACHE = json.load(f)
    except Exception:
        _SKILLS_CACHE = {}
    return _SKILLS_CACHE


def _buscar_salario_skill(funcao: str) -> float | None:
    """Busca salário de referência nos skills absorvidos do PNCP."""
    skills = _load_skills_pncp()
    salarios = skills.get("salarios_por_cargo", {})
    if not salarios:
        return None
    funcao_norm = _normalizar_texto(funcao)
    # Match exato
    for cargo, dados in salarios.items():
        if _normalizar_texto(cargo) == funcao_norm:
            return dados.get("media")
    # Match parcial
    palavras = [w for w in funcao_norm.split() if len(w) > 3]
    for cargo, dados in salarios.items():
        cargo_norm = _normalizar_texto(cargo)
        if any(w in cargo_norm for w in palavras) and dados.get("amostras", 0) >= 2:
            return dados.get("media")
    return None


def _selecionar_mdo_padrao(edital: dict, analise: dict) -> tuple[list[dict], str]:
    """Usa MDO padrão como base quando edital não fornece tabela de postos.

    A MDO padrão contém 56 funções com pisos SEAC/RJ.
    Seleciona funções relevantes ao objeto do edital.
    """
    mdo = _load_mdo_padrao()
    todos_postos = mdo.get("postos", [])
    objeto = (edital.get("objeto", "") or "").lower()

    # Mapeia categorias de funções por palavras-chave no objeto
    categorias = {
        "limpeza": ["auxiliar de limpeza", "faxineira", "servente", "limpador", "encarregado"],
        "copa": ["copeira", "cozinheira", "garçom", "auxiliar de cozinha", "chefe de cozinha"],
        "portaria": ["porteiro/vigia", "auxiliar de portaria", "operador de cftv", "controlador"],
        "administrativo": ["recepcionista", "auxiliar de escritório", "assistente administrativo", "mensageiro", "agente administrativo"],
        "manutencao": ["auxiliar de manutenção", "encarregado"],
        "jardinagem": ["auxiliar de jardinagem", "operador de roçadeira"],
    }

    # Detecta categorias relevantes
    keywords_map = {
        "limpeza": ["limpeza", "conservação", "asseio", "higienização", "facilities"],
        "copa": ["copeiragem", "copa", "cozinha", "alimentação", "refeição"],
        "portaria": ["portaria", "controle de acesso", "vigia", "cftv"],
        "administrativo": ["administrativo", "recepção", "secretaria", "apoio", "mão de obra"],
        "manutencao": ["manutenção", "predial"],
        "jardinagem": ["jardinagem", "paisagismo", "área verde"],
    }

    cats_ativas = set()
    for cat, kws in keywords_map.items():
        if any(kw in objeto for kw in kws):
            cats_ativas.add(cat)

    if not cats_ativas:
        cats_ativas = {"limpeza", "administrativo"}  # fallback genérico
        log.info("MDO padrão: sem match no objeto. Usando limpeza + administrativo como base.")

    # Seleciona funções das categorias ativas
    funcoes_selecionadas = set()
    for cat in cats_ativas:
        for nome in categorias.get(cat, []):
            funcoes_selecionadas.add(nome.lower())

    postos = []
    for p in todos_postos:
        if p["funcao"].lower() in funcoes_selecionadas:
            postos.append({
                "funcao": p["funcao_normalizada"],
                "funcao_display": p["funcao"],
                "quantidade": 1,
                "jornada": "44h",
                "salario_base": p["salario_base"],
                "periculosidade": p["periculosidade_pct"] > 0,
            })

    if not postos:
        # Fallback: pega as 5 funções mais comuns
        for p in todos_postos[:5]:
            postos.append({
                "funcao": p["funcao_normalizada"],
                "funcao_display": p["funcao"],
                "quantidade": 1,
                "jornada": "44h",
            })

    # Estima quantidade de postos baseado no valor estimado do edital
    # Custo médio por funcionário/mês (salário + encargos + benefícios + BDI) ≈ R$ 5.500
    valor_estimado = edital.get("valor_estimado", 0) or 0
    prazo = analise.get("prazo_contrato_meses") or 12
    if valor_estimado > 0 and postos:
        CUSTO_MEDIO_MENSAL = 5500
        total_func_estimado = max(1, round(valor_estimado / prazo / CUSTO_MEDIO_MENSAL))

        # SERVIÇO PONTUAL: se o valor total é pequeno (< 200k) OU o objeto indica
        # consultoria/estudo/análise/elaboração, trata como serviço pontual
        # (1 a 2 funcionários por no máximo o prazo que cabe no teto)
        servico_pontual_kws = ["elabora", "desenvolver", "análise", "analise", "estudo",
            "consultoria", "laboratori", "projeto", "diagnóstic", "diagnostic",
            "pontual", "remoção", "remocao", "desmontagem", "caminhões", "caminhoes"]
        eh_pontual = (
            valor_estimado < 200000
            or any(kw in objeto for kw in servico_pontual_kws)
        )

        if eh_pontual:
            # Reduz postos para caber no teto
            # 1 funcionário pelo prazo com ~80% do teto, para deixar margem
            custo_max_por_func = valor_estimado * 0.85 / prazo
            if custo_max_por_func < 2500:
                # Teto muito pequeno: apenas 1 posto simples
                postos = postos[:1]
                postos[0]["quantidade"] = 1
            else:
                postos = postos[:max(1, int(custo_max_por_func // 5500))]
                for p in postos:
                    p["quantidade"] = 1
            log.info(f"MDO padrão: SERVIÇO PONTUAL (R$ {valor_estimado:,.0f}). Usando {len(postos)} posto(s).")
        else:
            # Distribui proporcionalmente entre os postos
            n_funcoes = len(postos)
            for i, p in enumerate(postos):
                if i == 0:
                    p["quantidade"] = max(1, round(total_func_estimado * 0.6 / 1) if n_funcoes > 2 else round(total_func_estimado * 0.8))
                elif i == n_funcoes - 1 and n_funcoes > 2:
                    p["quantidade"] = max(1, round(total_func_estimado / 30))
                else:
                    restante = total_func_estimado - postos[0]["quantidade"] - max(1, round(total_func_estimado / 30))
                    p["quantidade"] = max(1, round(restante / max(1, n_funcoes - 2)))
            log.info(f"MDO padrão: estimativa {total_func_estimado} funcionários para valor R$ {valor_estimado:,.0f} / {prazo} meses")

    perfil_nome = "+".join(sorted(cats_ativas))
    log.info(f"MDO padrão ({perfil_nome}): {len(postos)} funções, {sum(p['quantidade'] for p in postos)} funcionários")
    return postos, perfil_nome


def _selecionar_melhor_empresa(postos_raw: list, analise: dict, edital: dict) -> dict:
    """Seleciona a empresa do grupo com menor custo para este edital.

    Considera: regime tributário, desoneração, RAT/FAP, restrições.
    Retorna dict com dados da empresa selecionada.
    """
    empresas = _load_empresa_perfil()
    uf = edital.get("uf", "RJ")
    esfera = "federal" if edital.get("orgao_nome", "").lower().startswith(("ministerio", "ibge", "inss", "inpe")) else "estadual"

    # Filtra empresas viáveis
    viaveis = []
    for emp in empresas:
        # Checa restrição de sanção
        sancao = emp.get("restricoes", {}).get("sancao_agu", {})
        if sancao.get("ativa"):
            # Sanção AGU de abrangência nacional bloqueia TODAS as esferas
            abrangencia = sancao.get("abrangencia", "nacional")
            bloqueia = False
            if abrangencia == "nacional":
                bloqueia = True  # Bloqueia federal, estadual E municipal
            elif abrangencia == "federal" and esfera == "federal":
                bloqueia = True
            elif abrangencia == "estadual" and esfera in ("estadual", "municipal"):
                bloqueia = True

            if bloqueia:
                from datetime import date, datetime
                vigencia = sancao.get("vigencia_ate", "")
                try:
                    if datetime.strptime(vigencia, "%Y-%m-%d").date() > date.today():
                        log.info(f"  {emp['nome']}: DESCARTADA (sanção {abrangencia})")
                        continue
                except ValueError:
                    log.info(f"  {emp['nome']}: DESCARTADA (sanção ativa, vigência inválida)")
                    continue

        # Checa UF
        if uf not in emp.get("uf_atuacao", []):
            log.info(f"  {emp['nome']}: DESCARTADA (não atua em {uf})")
            continue

        # Checa se presta o tipo de serviço
        servicos = emp.get("servicos", [])
        objeto = (edital.get("objeto", "") or "").lower()
        match_servico = any(s.lower() in objeto for s in servicos)
        if not match_servico:
            # Tenta match por postos
            for p in postos_raw:
                funcao = (p.get("funcao", "") or "").lower()
                if any(s.lower() in funcao or funcao in s.lower() for s in servicos):
                    match_servico = True
                    break

        viaveis.append({
            **emp,
            "match_servico": match_servico,
        })

    if not viaveis:
        log.warning("Nenhuma empresa viável. Usando Manutec como fallback.")
        return empresas[0]

    # Prioriza: match de serviço + desonerada + menor tributo
    def score_empresa(e):
        score = 0
        if e.get("match_servico"):
            score += 100
        if e.get("desonerada"):
            score += 50
        # Menor tributo = melhor
        if e.get("regime_tributario") == "lucro_real":
            pis = e.get("pis_efetivo_pct", 1.0)
            cofins = e.get("cofins_efetivo_pct", 4.5)
            score += (10 - pis - cofins)  # Quanto menor, mais pontos
        return score

    viaveis.sort(key=score_empresa, reverse=True)
    melhor = viaveis[0]
    log.info(f"  Empresa selecionada: {melhor['nome']} (desonerada={melhor.get('desonerada')}, regime={melhor.get('regime_tributario')})")
    return melhor

log = logging.getLogger("agente3_precificador")

PLANILHAS_DIR = DATA_DIR / "planilhas"


def _extrair_postos_llm(edital: dict, analise: dict) -> dict:
    """Usa Claude para extrair postos e parâmetros do edital analisado."""
    postos_analise = analise.get("postos", [])
    postos_texto = ""
    if postos_analise:
        for p in postos_analise:
            if isinstance(p, dict):
                postos_texto += f"- {p.get('funcao', '?')}: {p.get('quantidade', 1)} postos, jornada {p.get('jornada', '44h')}\n"
            else:
                postos_texto += f"- {p}\n"
    else:
        postos_texto = "Não identificados na análise prévia."

    requisitos = analise.get("requisitos_habilitacao", [])
    requisitos_texto = "\n".join(f"- {r}" for r in requisitos) if requisitos else "Não especificados."

    prompt = PROMPT_EXTRAIR_POSTOS.format(
        objeto=edital.get("objeto", ""),
        valor_estimado=f"{edital.get('valor_estimado', 0):,.2f}",
        municipio=edital.get("municipio", "Rio de Janeiro"),
        uf=edital.get("uf", "RJ"),
        empresa_sugerida=edital.get("empresa_sugerida", "manutec"),
        prazo_meses=analise.get("prazo_contrato_meses", 12) or 12,
        postos_texto=postos_texto,
        requisitos_texto=requisitos_texto,
        regime_contratacao=analise.get("regime_contratacao", ""),
        cct_aplicavel=analise.get("cct_aplicavel", ""),
        local_prestacao=analise.get("local_prestacao", ""),
        observacoes="",
    )

    return ask_claude_json(
        system=SYSTEM_EXTRAIR_POSTOS,
        user=prompt,
        max_tokens=3000,
        agente="precificador",
        pncp_id=edital.get("pncp_id"),
    )


def _normalizar_texto(t: str) -> str:
    """Remove acentos e normaliza para comparação."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).replace("_", " ").replace("-", " ")


def _buscar_mdo_padrao(funcao: str) -> dict | None:
    """Busca função na MDO padrão do grupo (planilha real com pisos SEAC/RJ)."""
    try:
        mdo = _load_mdo_padrao()
        postos = mdo.get("postos", [])
        funcao_norm = _normalizar_texto(funcao)

        # Match exato primeiro
        for p in postos:
            if _normalizar_texto(p["funcao"]) == funcao_norm:
                return p

        # Match parcial (busca palavras-chave)
        palavras = [w for w in funcao_norm.split() if len(w) > 2]
        melhor_match = None
        melhor_score = 0
        for p in postos:
            nome = _normalizar_texto(p["funcao"])
            score = sum(1 for w in palavras if w in nome)
            if score > melhor_score:
                melhor_score = score
                melhor_match = p

        if melhor_match and melhor_score >= 1:
            return melhor_match

    except Exception as e:
        log.warning(f"Erro ao buscar MDO padrão: {e}")
    return None


def _resolver_salario(funcao: str, salario_edital: float | None,
                      sindicato: str, uf: str,
                      pisos_edital: dict | None = None,
                      sem_api: bool = False) -> float:
    """Determina salário com prioridade:
    1. Piso explícito no edital (extraído pelo Agente 2)
    2. MDO padrão do grupo (planilha real com pisos SEAC/RJ) ← NOVO
    3. Salário informado pelo LLM na extração de postos
    4. Piso da CCT no banco local (data/ccts/*.json)
    5. Estimativa via LLM baseada na CCT identificada
    6. Salário mínimo 2026
    """
    # 1. Piso do edital (CCT mencionada no edital com valores)
    if pisos_edital:
        funcao_norm = funcao.lower().replace(" ", "_").replace("-", "_")
        for k, v in pisos_edital.items():
            if funcao_norm in k or k in funcao_norm:
                log.info(f"Salário {funcao}: R$ {v:.2f} (piso do edital)")
                return v

    # 2. MDO padrão do grupo (pisos reais SEAC/RJ)
    mdo_match = _buscar_mdo_padrao(funcao)
    if mdo_match:
        sal = mdo_match["salario_base"]
        log.info(f"Salário {funcao}: R$ {sal:.2f} (MDO padrão - {mdo_match['funcao']})")
        return sal

    # 3. Salário do LLM
    if salario_edital and salario_edital > 0:
        return salario_edital

    # 4. Piso da CCT local
    piso = get_piso_salarial(sindicato, uf, funcao)
    if piso:
        log.info(f"Salário {funcao}: R$ {piso:.2f} (CCT {sindicato})")
        return piso

    # 4.5. SKILL PNCP: salário médio extraído de planilhas reais de licitações ganhas
    skill_salario = _buscar_salario_skill(funcao)
    if skill_salario and skill_salario > 500:  # Sanity check
        log.info(f"Salário {funcao}: R$ {skill_salario:.2f} (SKILL PNCP - planilhas vencedoras)")
        return skill_salario

    # 5. Estimativa via LLM para CCTs não cadastradas (pula se sem_api)
    if not sem_api:
        try:
            piso_llm = _estimar_piso_llm(funcao, sindicato, uf)
            if piso_llm and piso_llm > 0:
                log.info(f"Salário {funcao}: R$ {piso_llm:.2f} (estimativa LLM para {sindicato})")
                return piso_llm
        except Exception as e:
            log.warning(f"Erro ao estimar piso via LLM: {e}")

    # 6. Salário mínimo
    log.warning(f"Sem piso para {funcao} ({sindicato}/{uf}). Usando salário mínimo.")
    return 1518.00


def _estimar_piso_llm(funcao: str, sindicato: str, uf: str) -> float | None:
    """Usa LLM para estimar piso salarial baseado na CCT identificada."""
    prompt = f"""Qual o piso salarial aproximado para a função "{funcao}" na CCT do sindicato {sindicato} no estado {uf}?

Considere:
- Valores vigentes em 2025/2026
- Se não conhecer a CCT exata, use como referência CCTs similares do mesmo segmento e região
- O valor deve ser realista para o mercado de terceirização de serviços no {uf}

Responda SOMENTE com JSON: {{"piso_estimado": <float>, "fonte": "<nome da CCT de referência>", "confianca": "<alta|media|baixa>"}}"""

    resultado = ask_claude_json(
        system="Você é especialista em CCTs e pisos salariais de terceirização no Brasil.",
        user=prompt,
        max_tokens=200,
        agente="precificador",
    )
    if resultado and resultado.get("piso_estimado"):
        return float(resultado["piso_estimado"])
    return None


def _montar_kwargs_beneficios(sindicato: str, uf: str, params: dict) -> dict:
    """Monta kwargs de benefícios a partir da CCT, skills PNCP e parâmetros."""
    beneficios = get_beneficios(sindicato, uf)
    kwargs = {}

    # SKILL PNCP: benefícios médios de planilhas reais vencedoras
    skills = _load_skills_pncp()
    skill_benef = skills.get("beneficios_media", {})

    vt = beneficios.get("vale_transporte", {})
    if vt:
        kwargs["desconto_vt_pct"] = vt.get("desconto_empregado_pct", 6.0)
    # Tarifa VT da skill PNCP (média real)
    if skill_benef.get("vale_transporte") and skill_benef["vale_transporte"] > 100:
        # Skill armazena total mensal — converte para tarifa dia: tot/22/2
        kwargs["tarifa_vt"] = round(skill_benef["vale_transporte"] / 22 / 2, 2)
        log.info(f"  SKILL PNCP: tarifa VT = R$ {kwargs['tarifa_vt']:.2f}")

    va = beneficios.get("vale_alimentacao", {})
    if va:
        kwargs["vale_alimentacao_dia"] = va.get("valor_dia", 34.00)
        kwargs["dias_alimentacao"] = va.get("dias_mes", 22)
        kwargs["desconto_va_pct"] = va.get("desconto_empregado_pct", 1.0)
    elif skill_benef.get("vale_alimentacao_dia"):
        kwargs["vale_alimentacao_dia"] = skill_benef["vale_alimentacao_dia"]
        log.info(f"  SKILL PNCP: VA dia = R$ {kwargs['vale_alimentacao_dia']:.2f}")

    cb = beneficios.get("cesta_basica", {})
    if cb:
        kwargs["cesta_basica"] = cb.get("valor_mensal", 183.26)
    elif skill_benef.get("cesta_basica"):
        kwargs["cesta_basica"] = skill_benef["cesta_basica"]
        log.info(f"  SKILL PNCP: cesta básica = R$ {kwargs['cesta_basica']:.2f}")

    sv = beneficios.get("seguro_vida", {})
    if sv:
        kwargs["seguro_vida"] = sv.get("valor_mensal_por_empregado", 15.00)

    if params.get("plano_saude_obrigatorio"):
        kwargs["plano_saude"] = params.get("valor_plano_saude", 200.00)

    return kwargs


def _eh_obra(edital: dict) -> bool:
    """Detecta se o edital é obra/engenharia (usa BDI) vs terceirização de MDO (usa CI+Lucro).

    BDI é componente específico de obras (TCU/Súmula 253). Para MDO (IN 05/2017),
    o markup é composto por CI + Lucro + Tributos, sem BDI.
    """
    obj = (edital.get("objeto") or "").lower()
    palavras_obra = [
        "obra", "construção", "construcao", "reforma", "ampliação", "ampliacao",
        "pavimentação", "pavimentacao", "edificação", "edificacao",
        "urbanização", "urbanizacao", "drenagem", "recuperação estrutural",
        "impermeabilização", "impermeabilizacao", "engenharia civil",
        "infraestrutura", "construir", "reformar",
    ]
    palavras_mdo_forte = [
        "terceirização", "terceirizacao", "dedicação exclusiva", "dedicacao exclusiva",
        "apoio administrativo", "recepção", "portaria", "copeiragem",
        "vigilância", "limpeza e conservação", "limpeza e conservacao",
        "serviços continuados", "servicos continuados", "mão de obra",
        "mao de obra",
    ]
    if any(k in obj for k in palavras_mdo_forte):
        return False
    return any(k in obj for k in palavras_obra)


def precificar_edital(pncp_id: str, sem_api: bool = False, valor_alvo: float = None) -> dict | None:
    """Pipeline completo de precificação para um edital.

    Fluxo:
    1. Carrega edital e análise do banco
    2. Extrai postos via LLM (ou MDO padrão se sem_api=True)
    3. Para cada posto: resolve salário (CCT/edital) + calcula módulos 1-5
    4. Simula BDI (3 cenários)
    5. Gera planilha .xlsx
    6. Atualiza banco com resultado

    Args:
        sem_api: Se True, não faz chamadas LLM. Usa MDO padrão + CCT + salário mínimo.

    Returns:
        Dict com resultado ou None se falhar.
    """
    edital = get_edital(pncp_id)
    if not edital:
        log.error(f"Edital {pncp_id} não encontrado no banco.")
        return None

    analise_raw = edital.get("analise_json")
    if not analise_raw:
        log.warning(f"Edital {pncp_id} sem análise prévia. Usando dados básicos.")
        analise = {}
    else:
        analise = json.loads(analise_raw) if isinstance(analise_raw, str) else analise_raw

    # 1. Extrair postos — prioriza dados da tabela PDF (gratuito)
    postos_tabela = analise.get("postos_trabalho", [])
    fonte_postos = analise.get("_postos_fonte", "")

    if fonte_postos in ("tabela_pdf", "manual") and postos_tabela:
        # Postos já extraídos da tabela do PDF — não precisa de LLM
        log.info(f"Usando {len(postos_tabela)} postos extraídos da tabela PDF (sem custo LLM)")
        postos_raw = []
        for p in postos_tabela:
            postos_raw.append({
                "funcao": p.get("funcao", ""),
                "funcao_display": p.get("funcao_display", ""),
                "quantidade": p.get("quantidade", 1),
                "jornada": p.get("jornada", "44h"),
                "periculosidade": False,
                "insalubridade": None,
                "noturno": False,
                "salario_edital": None,
            })
        params = {
            "sindicato_sugerido": "SEAC-RJ",
            "uf": edital.get("uf", "RJ"),
            "prazo_meses": analise.get("prazo_contrato_meses") or 12,
            "municipio": edital.get("municipio", "Rio de Janeiro"),
        }
    elif not sem_api:
        # Fallback: usa LLM para extrair postos
        try:
            dados_postos = _extrair_postos_llm(edital, analise)
        except Exception as e:
            log.error(f"Erro ao extrair postos: {e}")
            atualizar_status_edital(pncp_id, "erro_precificacao", motivo_nogo=str(e))
            return None
        postos_raw = dados_postos.get("postos", [])
        params = dados_postos.get("parametros", {})
    else:
        # sem_api=True e sem postos da tabela PDF/manual — vai cair no MDO padrão abaixo
        postos_raw = []
        params = {}

    if not postos_raw:
        # Fallback: usa MDO padrão do grupo
        log.info(f"Sem postos extraídos. Usando MDO padrão como base.")
        try:
            postos_mdo, perfil_mdo = _selecionar_mdo_padrao(edital, analise)
            if postos_mdo:
                postos_raw = [
                    {
                        "funcao": p.get("funcao", ""),
                        "funcao_display": p.get("funcao_display", ""),
                        "quantidade": p.get("quantidade", 1),
                        "jornada": p.get("jornada", "44h"),
                        "periculosidade": False,
                        "insalubridade": None,
                        "noturno": False,
                        "salario_edital": None,
                    }
                    for p in postos_mdo
                ]
                fonte_postos = "mdo_padrao"
                log.info(f"MDO padrão '{perfil_mdo}': {len(postos_raw)} postos, {sum(p['quantidade'] for p in postos_raw)} funcionários")
        except Exception as e:
            log.warning(f"Erro ao carregar MDO padrão: {e}")

    if not postos_raw:
        log.warning(f"Nenhum posto extraído para {pncp_id}")
        atualizar_status_edital(pncp_id, "erro_precificacao",
                                motivo_nogo="Nenhum posto de trabalho identificado")
        return None

    # === VALIDAÇÃO: total de postos deve bater com o edital ===
    total_postos_extraidos = sum(p.get("quantidade") or 1 for p in postos_raw)
    valor_estimado = edital.get("valor_estimado", 0) or 0
    if valor_estimado > 0 and total_postos_extraidos > 0:
        custo_medio_por_posto = valor_estimado / 12 / total_postos_extraidos
        if custo_medio_por_posto > 10000 or custo_medio_por_posto < 2000:
            log.warning(
                f"⚠ VALIDAÇÃO: custo médio por posto = R$ {custo_medio_por_posto:,.2f}. "
                f"Faixa esperada: R$ 2.000 a R$ 10.000. "
                f"Total postos extraídos: {total_postos_extraidos}. "
                f"Valor estimado edital: R$ {valor_estimado:,.2f}. "
                f"POSSÍVEL ERRO na extração de postos!"
            )
            adicionar_comentario(
                pncp_id=pncp_id,
                tipo="alerta",
                texto=f"Custo médio por posto (R$ {custo_medio_por_posto:,.2f}) fora da faixa. Verificar se todos os postos foram extraídos.",
                autor="Agente3-Validador",
            )

    # Resolver CCT: prioriza o que o Agente 2 extraiu do edital
    cct_info = analise.get("cct_aplicavel", {})
    if isinstance(cct_info, str):
        # Compatibilidade: se veio como string simples
        sindicato = cct_info if cct_info != "não especificada" else params.get("sindicato_sugerido", "SEAC-RJ")
        pisos_edital = {}
    else:
        sindicato = cct_info.get("sindicato") or params.get("sindicato_sugerido", "SEAC-RJ")
        # Pisos mencionados no edital têm prioridade máxima
        pisos_edital = {}
        for p in (cct_info.get("pisos_mencionados") or []):
            if p.get("funcao") and p.get("piso"):
                pisos_edital[p["funcao"].lower().replace(" ", "_")] = p["piso"]

    uf = params.get("uf", edital.get("uf", "RJ"))
    prazo_meses = params.get("prazo_meses", 12) or 12

    # === SELEÇÃO INTELIGENTE DE EMPRESA ===
    empresa_perfil = _selecionar_melhor_empresa(postos_raw, analise, edital)
    empresa_nome = empresa_perfil["nome"]

    # Usa dados reais da empresa selecionada
    regime = empresa_perfil.get("regime_tributario", "lucro_real")
    desonerado = empresa_perfil.get("desonerada", False)
    rat_pct = empresa_perfil.get("rat_ajustado_pct", empresa_perfil.get("rat_pct", 3.0))

    municipio = params.get("municipio", edital.get("municipio", "Rio de Janeiro"))

    # Tributos com valores reais da empresa (PIS/COFINS efetivo após créditos)
    tributos_kwargs = {}
    if regime == "lucro_real":
        tributos_kwargs["pis_efetivo_pct"] = empresa_perfil.get("pis_efetivo_pct", 1.0)
        tributos_kwargs["cofins_efetivo_pct"] = empresa_perfil.get("cofins_efetivo_pct", 4.5)

    tributos_info = calcular_tributos(regime, municipio, **tributos_kwargs)
    tributos_pct = tributos_info["total_pct"]

    log.info(f"  Regime: {regime} | Desonerada: {desonerado} | RAT: {rat_pct}% | Tributos: {tributos_pct}%")

    # CI/Lucro conservador. O BREAK-EVEN simula cenários de 0% a 3%.
    # Usar 3%/3% como base garante que o valor proposta cobre custos + margem mínima.
    # O dashboard mostra os cenários para o usuário decidir.
    ci_pct = 3.0
    lucro_pct = 3.0

    # CALIBRAÇÃO POR VALOR ALVO: calcula Lucro para fechar EXATO no valor desejado
    if valor_alvo and valor_alvo > 0:
        # Dry-run: calcula postos com CI=0, Lucro=0 pra saber o custo direto (M1-M5 + tributos)
        kwargs_dry = _montar_kwargs_beneficios(sindicato, uf, params)
        custo_direto_anual = 0
        for p_raw in postos_raw:
            funcao_dry = p_raw.get("funcao", "")
            sal_dry = _resolver_salario(funcao_dry, p_raw.get("salario_edital"), sindicato, uf,
                                          pisos_edital=pisos_edital, sem_api=sem_api)
            qtd_dry = p_raw.get("quantidade") or 1
            r_dry = calcular_posto_completo(
                salario_base=sal_dry, jornada=p_raw.get("jornada", "44h"),
                adicional_periculosidade=p_raw.get("periculosidade", False),
                adicional_insalubridade=p_raw.get("insalubridade"),
                adicional_noturno=p_raw.get("noturno", False),
                rat_pct=rat_pct, desonerado=desonerado,
                ci_pct=0, lucro_pct=0, tributos_pct=tributos_pct,
                **kwargs_dry,
            )
            custo_direto_anual += r_dry["valor_mensal_posto"] * qtd_dry * 12

        if custo_direto_anual > 0:
            # REGRAS LEGAIS FIXAS (não podem ser mexidas):
            #   - CCT: pisos salariais obrigatórios por lei
            #   - Tributos: obrigação fiscal (PIS/COFINS/ISS)
            # AJUSTÁVEL: apenas Lucro (mínimo 0%) e Custos Indiretos (mínimo 0%).
            #
            # Fórmula IN 05/2017:
            #   valor_final = custo_m1_m5 * (1 + CI/100 + Lucro/100) / (1 - tributos/100)
            # Dry-run (CI=0, Lucro=0): valor_final = custo_m1_m5 / (1 - tributos/100)
            tributos_frac = tributos_pct / 100
            custo_m1_m5_anual = custo_direto_anual * (1 - tributos_frac)
            # Mínimo absoluto: custo direto + tributos (CI=0, Lucro=0)
            minimo_absoluto = custo_m1_m5_anual / (1 - tributos_frac)

            if valor_alvo < minimo_absoluto:
                log.warning(
                    f"⚠ VALOR ALVO R$ {valor_alvo:,.2f} ESTÁ ABAIXO do custo mínimo legal "
                    f"(CCT + tributos) R$ {minimo_absoluto:,.2f}. "
                    f"Usando mínimo viável com CI=0%, Lucro=0%."
                )
                valor_alvo = minimo_absoluto
                ci_pct = 0.0
                lucro_pct = 0.0
            else:
                # Resolve: valor_alvo = custo_m1_m5 * (1 + CI + Lucro) / (1 - tributos)
                # Distribui excedente entre CI (3%) e Lucro (restante)
                total_marg_pct = (valor_alvo * (1 - tributos_frac) / custo_m1_m5_anual - 1) * 100
                if total_marg_pct <= 3.0:
                    # Pouco espaço: só CI, sem Lucro
                    ci_pct = max(0.0, total_marg_pct)
                    lucro_pct = 0.0
                else:
                    ci_pct = 3.0
                    lucro_pct = total_marg_pct - ci_pct
            log.info(f"CALIBRADO (respeitando CCT+tributos): "
                     f"custo M1-M5 R$ {custo_m1_m5_anual:,.2f} → alvo R$ {valor_alvo:,.2f} "
                     f"→ CI={ci_pct:.2f}%, Lucro={lucro_pct:.2f}%, Tributos={tributos_pct}% (fixo)")

    # 2. Calcular cada posto
    postos_calculados = []
    kwargs_beneficios = _montar_kwargs_beneficios(sindicato, uf, params)

    for posto_raw in postos_raw:
        funcao = posto_raw.get("funcao", "servente_limpeza")
        quantidade = posto_raw.get("quantidade") or 1

        salario = _resolver_salario(
            funcao, posto_raw.get("salario_edital"), sindicato, uf,
            pisos_edital=pisos_edital, sem_api=sem_api,
        )

        # Enriquecer com dados da MDO padrão (periculosidade, VR, etc.)
        mdo_ref = _buscar_mdo_padrao(funcao)
        periculosidade = posto_raw.get("periculosidade", False)
        insalubridade = posto_raw.get("insalubridade")
        noturno = posto_raw.get("noturno", False)

        if mdo_ref and not periculosidade:
            if mdo_ref.get("periculosidade_pct", 0) > 0:
                periculosidade = True
                log.info(f"  {funcao}: periculosidade ativada pela MDO padrão")

        # VR da MDO padrão
        if mdo_ref:
            vr_dia = mdo_ref.get("vr_dia", 23.5)
            dias_vr = mdo_ref.get("dias_vr", 22)
            if "vale_alimentacao_dia" not in kwargs_beneficios:
                kwargs_beneficios["vale_alimentacao_dia"] = vr_dia
                kwargs_beneficios["dias_alimentacao"] = dias_vr

        resultado_posto = calcular_posto_completo(
            salario_base=salario,
            jornada=posto_raw.get("jornada", "44h"),
            adicional_periculosidade=periculosidade,
            adicional_insalubridade=insalubridade,
            adicional_noturno=noturno,
            rat_pct=rat_pct,
            desonerado=desonerado,
            ci_pct=ci_pct,
            lucro_pct=lucro_pct,
            tributos_pct=tributos_pct,
            **kwargs_beneficios,
        )

        resultado_posto["nome"] = posto_raw.get("funcao_display", funcao.replace("_", " ").title())
        resultado_posto["funcao"] = funcao
        resultado_posto["quantidade"] = quantidade
        resultado_posto["salario_base"] = salario

        postos_calculados.append(resultado_posto)
        log.info(
            f"  Posto {resultado_posto['nome']}: "
            f"R$ {resultado_posto['valor_mensal_posto']:,.2f}/mês × {quantidade}"
        )

    # 3. Simulação BDI (4 cenários agora)
    custo_direto_total = sum(
        p["subtotal_m1_m4"] * p["quantidade"] for p in postos_calculados
    )
    valor_ref_mensal = (edital.get("valor_estimado") or 0) / prazo_meses if prazo_meses > 0 else 0

    cenarios_bdi = simular_cenarios(
        custo_direto_mensal=custo_direto_total,
        valor_referencia_mensal=valor_ref_mensal,
        prazo_meses=prazo_meses,
        tributos_pct=tributos_pct,
    )

    # 4. Gerar planilha
    PLANILHAS_DIR.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"planilha_{pncp_id.replace('/', '_').replace('-', '_')}.xlsx"
    output_path = PLANILHAS_DIR / nome_arquivo

    # Info da empresa para a planilha
    info_empresa = {
        "nome": empresa_nome,
        "regime": regime,
        "desonerada": desonerado,
        "rat_pct": rat_pct,
        "tributos_pct": tributos_pct,
        "tributos_detalhe": tributos_info,
    }

    # Converte postos_calculados para formato do novo builder
    cargos_builder = []
    tarifa_vt = kwargs_beneficios.get("tarifa_vt", 4.70)
    va_dia = kwargs_beneficios.get("vale_alimentacao_dia", 25.0)
    dias_va = kwargs_beneficios.get("dias_alimentacao", 22)
    desc_vt = kwargs_beneficios.get("desconto_vt_pct", 6.0)
    desc_vt = desc_vt / 100 if desc_vt > 1 else desc_vt
    desc_va = kwargs_beneficios.get("desconto_va_pct", 10.0)
    desc_va = desc_va / 100 if desc_va > 1 else desc_va

    for p in postos_calculados:
        sal = p.get("salario_base", 0)
        # VT líquido = (tarifa * 2 * 22) - (6% * salário)
        vt_bruto = tarifa_vt * 2 * 22
        vt_desconto = sal * desc_vt
        vt_liquido = max(0, vt_bruto - vt_desconto)
        # VA líquido = (valor_dia * dias) - (desconto% * valor_dia * dias)
        va_bruto = va_dia * dias_va
        va_liquido = va_bruto * (1 - desc_va)

        # Detecta adicionais
        insalub_pct = 0
        if p.get("adicional_insalubridade_valor", 0) > 0 and sal > 0:
            insalub_pct = round(p["adicional_insalubridade_valor"] / sal * 100)
            if insalub_pct not in (20, 40):
                insalub_pct = 20  # default

        peric_pct = 30 if p.get("adicional_periculosidade_valor", 0) > 0 else 0

        cargos_builder.append({
            "funcao": p.get("nome", "CARGO"),
            "quantidade": p.get("quantidade", 1),
            "jornada": p.get("jornada", "44h"),
            "salario_base": sal,
            "adicional_insalubridade_pct": insalub_pct,
            "adicional_periculosidade_pct": peric_pct,
            "adicional_noturno": p.get("adicional_noturno_valor", 0) > 0,
            "vt": vt_liquido,
            "va": va_liquido,
            "cesta_basica": kwargs_beneficios.get("cesta_basica", 0),
            "bsf": kwargs_beneficios.get("bsf", 0),
            "seguro_vida": kwargs_beneficios.get("seguro_vida", 0),
            "uniformes": p.get("uniformes_mensal", 90),
            "materiais": p.get("materiais_mensal", 0),
            "equipamentos": p.get("equipamentos_mensal", 0),
        })

    empresa_builder = {
        "nome": empresa_nome,
        "regime": "Lucro Real" if regime == "lucro_real" else regime,
        # empresa_perfil tem valores em % (ex: 0.05 = 0.05%, 4.15 = 4.15%)
        # planilha_builder espera decimal (ex: 0.0005, 0.0415)
        "pis_pct": empresa_perfil.get("pis_efetivo_pct", 0.05) / 100,
        "cofins_pct": empresa_perfil.get("cofins_efetivo_pct", 4.15) / 100,
        "iss_pct": tributos_info.get("iss_pct", 2.0) / 100,
        "sat_rat_pct": rat_pct / 100,
        "ci_pct": ci_pct / 100,
        "lucro_pct": lucro_pct / 100,
    }

    edital_builder = {
        "orgao": edital.get("orgao_nome", ""),
        "pregao": pncp_id,
        "objeto": edital.get("objeto", "")[:60],
        "valor_teto": edital.get("valor_estimado") or 0,
        "cct_nome": sindicato or "SEAC-RJ",
        "prazo_meses": prazo_meses,
    }

    # Detecta se o edital ja fornece planilha/modelo de proposta
    editais_dir = DATA_DIR / "editais"
    tpl_info = detectar_template_info(editais_dir, pncp_id)
    template_preenchido_path = None
    template_aviso = None

    if tpl_info:
        # Classifica o template para garantir compatibilidade com o tipo do edital
        clf = classificar_planilha(tpl_info["path"])
        tipo_esperado = "obra" if _eh_obra(edital) else "mdo"
        tipo_detectado = clf.get("tipo", "desconhecido")
        if tipo_detectado not in (tipo_esperado, "desconhecido") and clf.get("confianca", 0) >= 0.3:
            template_aviso = (
                f"⚠ Template do edital é tipo '{tipo_detectado}' (conf {clf['confianca']}) "
                f"mas edital é '{tipo_esperado}'. NÃO preenchendo — conferir {tpl_info['path'].name}."
            )
            log.warning(template_aviso)
            tpl_info = None  # nao tenta preencher
    if tpl_info:
        if tpl_info["fillable"] and pode_usar_template(tpl_info["path"]):
            try:
                tpl_out = PLANILHAS_DIR / f"planilha_{pncp_id.replace('/', '_').replace('-', '_')}_MODELO_ORGAO.xlsx"
                # Adapta cargos_builder -> formato do filler
                postos_fill = []
                for c in cargos_builder:
                    postos_fill.append({
                        "funcao": c["funcao"],
                        "salario": c["salario_base"],
                        "quantidade": c["quantidade"],
                        "jornada": c["jornada"],
                        "vt": c["vt"],
                        "va": c["va"],
                        "uniformes": c["uniformes"],
                        "materiais": c["materiais"],
                        "equipamentos": c["equipamentos"],
                        "periculosidade": c["adicional_periculosidade_pct"] / 100 if c["adicional_periculosidade_pct"] else 0,
                        "insalubridade": c["adicional_insalubridade_pct"] / 100 if c["adicional_insalubridade_pct"] else 0,
                        "seguro_vida": c["seguro_vida"],
                    })
                emp_fill = dict(empresa_builder)
                emp_fill["orgao"] = edital_builder["orgao"]
                emp_fill["pregao"] = edital_builder["pregao"]
                emp_fill["valor_edital"] = edital_builder["valor_teto"]
                preencher_template(tpl_info["path"], postos_fill, emp_fill, tpl_out)
                template_preenchido_path = tpl_out
                log.info(f"✓ Modelo do orgao preenchido automaticamente: {tpl_out.name}")
            except Exception as e:
                log.warning(f"Falha preenchendo template do orgao: {e}. Seguindo com modelo padrao.")
                template_aviso = f"Modelo do órgão ({tpl_info['path'].name}) não pôde ser preenchido automaticamente — preencher manualmente."
        else:
            template_aviso = f"⚠ Edital fornece modelo próprio: {tpl_info['path'].name} — {tpl_info['motivo']}"
            log.warning(template_aviso)

    # Gera planilha no formato padrao (referencia interna + break-even)
    try:
        gerar_planilha(postos=cargos_builder, empresa_info=empresa_builder, licitacao_info=edital_builder, output_path=output_path)
        log.info(f"Planilha (referencia) gerada: {output_path}")
    except Exception as e:
        log.error(f"Erro ao gerar planilha: {e}", exc_info=True)
        output_path = None

    # 5. Calcular valor proposta (cenário agressivo — para ser competitivo)
    cenario_escolhido = next(
        (c for c in cenarios_bdi if c["cenario"] == "agressivo"), cenarios_bdi[0]
    )
    # Se agressivo está abaixo de inexequibilidade, usa competitivo
    if not cenario_escolhido.get("acima_inexequibilidade", True):
        cenario_escolhido = next(
            (c for c in cenarios_bdi if c["cenario"] == "competitivo"),
            cenarios_bdi[1] if len(cenarios_bdi) > 1 else cenarios_bdi[0]
        )
        log.warning("Cenário agressivo abaixo do piso. Usando competitivo.")

    valor_proposta = cenario_escolhido["valor_global"]
    margem = cenario_escolhido.get("desconto_sobre_referencia_pct", 0)
    bdi = cenario_escolhido["bdi_pct"]

    # BDI só se aplica a OBRA. Para terceirização/MDO, markup é CI + Lucro (IN 05/2017).
    eh_obra = _eh_obra(edital)
    tipo_precificacao = "obra" if eh_obra else "mdo"
    if not eh_obra:
        bdi = None  # sinaliza N/A no dashboard

    # MODO ALVO: usuário definiu valor exato a fechar
    if valor_alvo and valor_alvo > 0:
        valor_proposta = valor_alvo
        valor_teto_calc = edital.get("valor_estimado") or 0
        if valor_teto_calc > 0:
            margem = (1 - valor_alvo / valor_teto_calc) * 100
        custo_direto_calc = sum(
            p["subtotal_m1_m4"] * p["quantidade"] for p in postos_calculados
        ) * 12
        if custo_direto_calc > 0 and eh_obra:
            bdi = (valor_alvo / custo_direto_calc - 1) * 100
        markup_label = f"BDI {bdi:.2f}%" if eh_obra and bdi is not None else "CI+Lucro"
        log.info(f"MODO ALVO: proposta calibrada para R$ {valor_alvo:,.2f} ({markup_label}, desconto {margem:.1f}%)")

    # SAFETY CAP: proposta nunca pode exceder o teto do edital
    # Se excedeu, significa que o MDO padrão superestimou os postos.
    # Reduz proporcionalmente para caber no teto com 5% de margem de segurança.
    valor_teto = edital.get("valor_estimado") or 0
    if valor_teto > 0 and valor_proposta > valor_teto:
        log.warning(
            f"⚠ Proposta R$ {valor_proposta:,.0f} EXCEDE teto R$ {valor_teto:,.0f}. "
            f"MDO padrão provavelmente inadequado (edital não é terceirização contínua). "
            f"Ajustando para 95% do teto."
        )
        valor_proposta = valor_teto * 0.95
        margem = 5.0  # 5% desconto sobre o teto
        bdi = 0 if eh_obra else None

    # 6. Atualizar banco
    atualizar_status_edital(
        pncp_id,
        status="precificado",
        planilha_path=str(output_path) if output_path else None,
        valor_proposta=valor_proposta,
        margem_percentual=margem,
        bdi_percentual=bdi if eh_obra else 0,
    )

    # Comentário automático
    resumo_postos = ", ".join(
        f"{p['nome']} ×{p['quantidade']}" for p in postos_calculados
    )
    economia_desoneracao = ""
    if desonerado:
        economia_desoneracao = " [DESONERADA — INSS patronal reduzido]"

    aviso_template = ""
    if template_preenchido_path:
        aviso_template = f" 📄 Modelo do órgão preenchido: {template_preenchido_path.name}."
    elif template_aviso:
        aviso_template = f" {template_aviso}"

    adicionar_comentario(
        pncp_id=pncp_id,
        tipo="precificacao",
        texto=(
            f"Precificação competitiva via {empresa_nome}.{economia_desoneracao} "
            f"Postos: {resumo_postos}. "
            f"Valor proposta: R$ {valor_proposta:,.2f} "
            f"({('BDI %.2f%%' % bdi) if eh_obra and bdi is not None else f'CI {ci_pct:.1f}%+Lucro {lucro_pct:.1f}%'}, desconto {margem:.1f}%). "
            f"Regime: {regime}, RAT: {rat_pct}%, Tributos: {tributos_pct}%."
            f"{aviso_template}"
        ),
        autor="Agente3-Precificador",
    )

    return {
        "pncp_id": pncp_id,
        "postos": postos_calculados,
        "cenarios_bdi": cenarios_bdi,
        "valor_proposta": valor_proposta,
        "margem_pct": margem,
        "bdi_pct": bdi,
        "planilha_path": str(output_path) if output_path else None,
        "tipo_precificacao": tipo_precificacao,
        "template_orgao_path": str(template_preenchido_path) if template_preenchido_path else None,
        "template_orgao_aviso": template_aviso,
        "template_orgao_origem": str(tpl_info["path"]) if tpl_info else None,
        "tributos": tributos_info,
        "parametros": params,
        "empresa": empresa_nome,
        "desonerada": desonerado,
    }


def executar_precificador(limit: int = 10) -> dict:
    """Processa editais com status 'analisado' e parecer 'go' ou 'go_com_ressalvas'.

    Returns:
        Stats dict com totais processados.
    """
    init_db()
    importar_ccts_diretorio()

    editais = get_editais_pendentes(status="analisado", limit=limit)

    # Filtra apenas os com parecer positivo
    editais_go = []
    for e in editais:
        parecer = e.get("parecer", "")
        if parecer in ("go", "go_com_ressalvas"):
            editais_go.append(e)

    log.info(f"Precificador: {len(editais_go)} editais para processar")

    resultados = {"total": len(editais_go), "sucesso": 0, "erro": 0}

    for edital in editais_go:
        pncp_id = edital["pncp_id"]
        log.info(f"Precificando: {pncp_id}")

        try:
            resultado = precificar_edital(pncp_id)
            if resultado:
                resultados["sucesso"] += 1
                _bdi_v = resultado.get("bdi_pct")
                _mk = f"BDI {_bdi_v:.2f}%" if (resultado.get("tipo_precificacao") == "obra" and _bdi_v is not None) else "CI+Lucro"
                log.info(
                    f"  OK: R$ {resultado['valor_proposta']:,.2f} "
                    f"({_mk})"
                )
            else:
                resultados["erro"] += 1
        except Exception as e:
            resultados["erro"] += 1
            log.error(f"  Erro: {e}")
            atualizar_status_edital(pncp_id, "erro_precificacao", motivo_nogo=str(e))

    log.info(
        f"Precificador concluído: {resultados['sucesso']}/{resultados['total']} OK, "
        f"{resultados['erro']} erros"
    )
    return resultados


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    init_db()
    stats = executar_precificador()
    print(f"\nResultado: {stats}")
