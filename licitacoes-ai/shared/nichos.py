"""Classificador de nicho + roteador de notificacoes Telegram.

Nichos: residuos, mdo_limpeza, seguranca, admin, obra, outros.
Cada nicho pode ter canal Telegram dedicado via env TELEGRAM_CHAT_<NICHO>.
"""
import logging
import os
import re
from dataclasses import dataclass

log = logging.getLogger("nichos")

NICHOS = ("residuos", "mdo_limpeza", "seguranca", "admin", "obra", "nautico", "aquisicao", "outros")

# Padroes que indicam AQUISICAO de produto (nao servico) — excluir dos nichos de servico
PADROES_AQUISICAO = [
    r"^aquisi[cç][aã]o\b",
    r"^fornecimento\b",
    r"^compra\b",
    # Aquisição em qualquer parte do texto (não só no início)
    r"\baquisi[cç][aã]o de\b",
    r"\bfornecimento de (materiais|equipamentos|produtos|g[eê]neros|insumos|sacos|tubos|conjuntos|condicionadores|contentor)\b",
    # Produtos de resíduos/limpeza que vazam pelo nicho residuos quando ofertados como AQUISIÇÃO
    r"^sacos? pl[aá]sticos?\b",  # ex.: "Sacos Plásticos Resíduos" (Fiocruz)
    r"^contentor(?:es)?\b",       # ex.: "CONTENTOR FLEXIVEL BIG BAG" (Casa da Moeda)
    r"^lixeira[s]?\b",
    r"^containers?\b",
    r"\bbig bag\b",
    # Seguros — vazam pelo nicho residuos quando objeto cita "viaturas/veículos"
    r"^seguro\b",
    r"\bseguro automotivo\b",
    r"\bseguro de veic[uú]los?\b",
]

# Contextos que INVALIDAM match de nautico
# (objetos administrativos/médicos/etc que aparecem em editais da Marinha mas não são produto/serviço náutico)
EXCLUSOES_NAUTICO = [
    # Climatização / refrigeração de ambiente
    r"\bar.?condicionado\b",
    r"\baparelhos? de ar.?condicionado\b",
    r"\bsplit\b",
    r"\bclimatiza[cç][aã]o\b",
    r"\brefrigera[cç][aã]o\b(?!.*(?:naval|n[aá]utica|marit|embarca|navio|motor de popa))",
    # Cestas, gêneros alimentícios, eventos
    r"\bcestas? b[aá]sicas?\b",
    r"\bg[eê]nero[s]? aliment[ií]cio[s]?\b",
    r"\bcoquetel\b",
    r"\bbuffet\b",
    r"\bpadaria\b",
    r"\brancho\b",
    # Cozinha (utensílios/equipamentos/material) — falso positivo Marinha (Navio-Patrulha Amazonas etc)
    r"\butens[ií]lios? de cozinha\b",
    r"\butens[ií]lios? dom[eé]sticos?\b",
    r"\bequipamentos? de cozinha\b",
    r"\bmaterial de cozinha\b",
    r"\bmateriais de cozinha\b",
    r"\bartigos? de cozinha\b",
    r"\bpanelas?\b",
    r"\btalheres?\b",
    r"\bfog[aã]o industrial\b",
    # TI / escritório
    r"\btoner[s]?\b",
    r"\bcartucho[s]?\b",
    r"\bimpressora[s]?\b",
    r"\bsoftware\b",
    r"\blicen[cç]a[s]? de uso\b",
    r"\blicenciamento de software\b",
    r"\badobe\b",
    r"\bmicrosoft\b",
    r"\bautocad\b",
    r"\bcomunica[cç][aã]o satelital\b",
    r"\bmaterial de escrit[oó]rio\b",
    r"\bpapel a4\b",
    # Móveis
    r"\bm[oó]veis?\b",
    r"\bmobili[aá]rio\b",
    r"\barm[aá]rio[s]?\b",
    # Brindes/comemorativos
    r"\bmoeda[s]? personalizada[s]?\b",
    r"\bmoeda[s]? comemorativa[s]?\b",
    r"\bmedalha[s]?\b",
    r"\bbrinde[s]?\b",
    r"\bplaca[s]? comemorativa[s]?\b",
    r"\bbandeira (oficial|comemorativa|representativa|institucional|do corpo)\b",
    # Saúde / cirurgia
    r"\binsumo[s]? cir[uú]rgico[s]?\b",
    r"\binstrumental cir[uú]rgico\b",
    r"\bplataforma de cirurgia\b",
    r"\bsistema integrado de cirurgia\b",
    r"\bhospitalar\b",
    r"\bm[eé]dico[-\s]hospitalar\b",
    r"\bodontol[oó]gico\b",
    r"\bcirurgia\b",
    r"\beletrocardi[oó]grafo\b",
    r"\bpolicl[ií]nica\b",
    r"\bsanat[oó]rio\b",
    r"\bcol[eé]gio\b",
    r"\bcomplexo naval\b",
    r"\bsa[uú]de\b(?!.*(?:n[aá]utica|naval|marit|embarca|navio))",
    # Pessoal/serviços administrativos
    r"\brecep[cç][aã]o\b",
    r"\bsecretariado\b",
    r"\bportaria predial\b",
    r"\bcredenciamento de pessoa[s]? jur[ií]dica[s]?\b",
    r"\bcredenciamento de profissional\b",
    r"\binscri[cç][aã]o (para|de|em)\b",
    # Armamento / militar (não é náutico)
    r"\bcanh[aã]o\b",
    r"\barmamento\b",
    r"\bmuni[cç][aã]o\b",
    r"\bfuzil\b",
    r"\bcarros? de combate\b",
    r"\bviatura[s]? blindada[s]?\b",
    r"\bfuzileiros? navais\b",
    r"\bcorpo de fuzileiros\b",
    # Veículos terrestres / seguro automotivo
    r"\bseguro automotivo\b",
    r"\bviatura[s]?\b(?!.*(?:lancha|embarca|navio))",
    # Bebedouros / utilidades prediais
    r"\bbebedouro[s]?\b",
    r"\bpiscina[s]?\b(?!.*(?:embarca|navio|lancha))",
    r"\bteto\b.*\blaje\b",
    r"\bjardinagem\b",
    r"\bpaisagismo\b",
    r"\bfardamento\b",
    r"\buniforme militar\b",
    r"\bgalavanizado\b",
    # Obras urbanas (não é manutenção naval)
    r"\bobras? de\b(?!.*(?:embarca|navio|estaleiro|casco|naval))",
    r"\bdrenagem urbana\b",
    r"\bgaleria de cintura\b",
    r"\bdes[aá]gue\b",
    # Limpeza predial (sem ser limpeza de casco)
    r"\blimpeza\b(?!.*(?:casco|embarca|navio|tanque))",
    # Eventos sociais / cultural (Iate Clube como local; almoço dançante etc)
    r"\biate clube\b",
    r"\bclube n[aá]utico\b",
    r"\balmo[cç]o dan[cç]ante\b",
    r"\bapresenta[cç][aã]o musical\b",
    r"\bartista\b",
    # Pesca como atividade educacional (não material)
    r"\bt[eé]cnico de pesca\b",
    r"\bpatr[aã]o de pesca\b",
    r"\bcurso de pesca\b",
    r"\bhoras?/?aula\b",
    r"\bhora-aula\b",
    # Gestão administrativa (mesmo de projeto naval, não é serviço técnico-naval)
    r"\bgest[aã]o administrativa e financeira\b",
    r"\bservi[cç]o de gest[aã]o\b",
    # Equipamento industrial — flanges/trocadores onde "casco" é peça mecânica
    r"\btrocador[es]? de calor\b",
    r"\bflange[s]?\b(?!.*(?:embarca|navio|naval|n[aá]utic|marit))",
    # Eventos comemorativos
    r"\bevento comemorativo\b",
    r"\bdia das? m[aã]es?\b",
    r"\bdia dos? pais?\b",
    r"\bdia das? crian[cç]as?\b",
]

# Contextos que INVALIDAM match de seguranca (falsos positivos conhecidos)
EXCLUSOES_SEGURANCA = [
    r"vigil[aâ]ncia (sanit[aá]ria|ambiental|em sa[uú]de|epidemiol[oó]gica|alimentar)",
    r"seguran[cç]a (do trabalho|alimentar|p[uú]blica|vi[aá]ria|da informa[cç][aã]o|h[ií]drica|nacional)",
    r"corpo de bombeiros",
    r"brigada de infantaria",
    r"brigada militar",
    r"recarga de extintor",
    r"manuten[cç][aã]o de extintor",
    r"an[aá]lises laboratoriais",
    r"prote[cç][aã]o radiol[oó]gica",
    r"seguran[cç]a nuclear",
]

# Keywords por nicho (ordem importa: residuos vence se tiver match)
KEYWORDS_NICHO = {
    "residuos": [
        # 20 keywords base (Sao Lourenco Ambiental)
        "resíduos", "residuos", "rejeito", "rejeitos",
        "reciclagem",
        "água oleosa", "agua oleosa", "borra oleosa",
        "efluente", "efluentes",
        "ete", "eta", "estação de tratamento", "estacao de tratamento",
        "lâmpada fluorescente", "lampada fluorescente",
        "pcb", "ascarel",
        "classe i", "classe ii", "classe 1", "classe 2",
        "descontaminação", "descontaminacao",
        "limpeza de tanque", "limpeza de tanques",
        "coleta seletiva",
        "destinação final", "destinacao final",
        "aterro sanitário", "aterro sanitario", "aterro industrial",
        "incineração", "incineracao",
        "offshore",
        "transporte de resíduo", "transporte de residuo",
        # +10 fortes
        "resíduo perigoso", "residuo perigoso",
        "resíduo sólido", "residuo solido",
        "resíduo hospitalar", "residuo hospitalar", "rss",
        "resíduo de construção", "residuo de construcao", "rcc", "entulho",
        "chorume",
        "mopp", "produtos perigosos",
        "slop", "slops",
        "lama de perfuração", "lama de perfuracao",
        "cascalho de perfuração", "cascalho de perfuracao",
        "logística reversa", "logistica reversa",
        "manifesto de transporte de resíduo", "manifesto de transporte de residuo", "mtr",
        # +7 moderados
        "licenciamento ambiental",
        "passivo ambiental",
        "remediação", "remediacao",
        "solo contaminado",
        "sucata",
        "descarte",
        "desativação de tanque", "desativacao de tanque",
        # locação de caçamba + destinação
        "locação de caçamba", "locacao de cacamba",
        "caçamba estacionária", "cacamba estacionaria",
        "caçamba roll", "cacamba roll",
        "roll-on", "roll-off",
        "transporte e destinação", "transporte e destinacao",
        "remoção de entulho", "remocao de entulho",
        "bota-fora", "bota fora",
    ],
    "mdo_limpeza": [
        "limpeza e conservação", "limpeza e conservacao",
        "asseio", "facilities", "zeladoria",
        "higienização hospitalar", "higienizacao hospitalar",
        "limpeza predial",
    ],
    "seguranca": [
        # Vigilância patrimonial (NUNCA "vigilância" sozinha — pega sanitaria/ambiental/saude)
        "vigilância patrimonial", "vigilancia patrimonial",
        "vigilância armada", "vigilancia armada",
        "vigilância desarmada", "vigilancia desarmada",
        "vigilância orgânica", "vigilancia organica",
        "vigilância noturna", "vigilancia noturna",
        "vigilância eletrônica", "vigilancia eletronica",
        # Segurança patrimonial (NUNCA "segurança" sozinha — pega do trabalho/alimentar/publica)
        "segurança patrimonial", "seguranca patrimonial",
        "segurança armada", "seguranca armada",
        "segurança desarmada", "seguranca desarmada",
        "segurança eletrônica", "seguranca eletronica",
        "segurança privada", "seguranca privada",
        # Controle de acesso (NUNCA "portaria" sozinha — pega Portaria nº/ministerial)
        "controlador de acesso", "controle de acesso",
        "posto de portaria", "serviço de portaria", "servico de portaria",
        "porteiro", "guarita",
        # Bombeiro civil / brigadista (NUNCA "brigada" sozinha — pega brigada militar/infantaria)
        "bombeiro civil", "brigadista de incêndio", "brigadista de incendio",
        "brigada de incêndio", "brigada de incendio",
        # Monitoramento eletrônico
        "monitoramento de alarme", "monitoramento de câmera",
        "monitoramento de camera", "cftv",
        "circuito fechado", "cerca elétrica", "cerca eletrica",
        "alarme monitorado", "central de monitoramento",
        # Escolta / transporte de valores
        "escolta armada", "transporte de valores",
        # Ronda / patrulhamento
        "ronda motorizada", "ronda ostensiva",
        "patrulhamento", "rondante",
    ],
    "admin": [
        "apoio administrativo", "recepção", "recepcao",
        "recepcionista", "copeiragem", "secretariado",
        "mensageria", "telefonista",
    ],
    "obra": [
        # NÃO usar "obra" sozinho — mesmo com word boundary do _match_kw,
        # casa em "mão de obra" (legitimamente, mas semanticamente é terceirização,
        # não obra civil). Sempre exigir contexto.
        "obras de", "obras civis", "obra civil", "obra pública", "obra publica",
        "obra de engenharia", "execução de obra", "execucao de obra",
        "conclusão de obra", "conclusao de obra",
        "construção", "construcao", "reforma",
        "ampliação", "ampliacao", "pavimentação", "pavimentacao",
        "drenagem", "engenharia civil", "edificação",
        "edificacao", "urbanização", "urbanizacao",
        "infraestrutura", "impermeabilização", "impermeabilizacao",
    ],
    "nautico": [
        # Escopo do canal POWER BOAT (decisão usuário 2026-05-20): SOMENTE
        # motor (todas variações), popa, lancha, manutenção de motor/lancha.
        # Embarcação genérica, navio, casco, estaleiro, cartas náuticas,
        # salvatagem, fretamento, eletrônica naval etc → NÃO entram mais.
        # ==== LANCHA ====
        "lancha", "lanchas",
        # ==== MOTORES E PROPULSÃO MARÍTIMA ====
        "motor de popa", "motor popa",
        "motores de popa", "motores popa",
        "motor de centro", "motor centro",
        "motores de centro", "motores centro",
        "motor marítimo", "motor maritimo",
        "motores marítimos", "motores maritimos",
        "motor marinizado", "motores marinizados",
        "motor naval", "motores navais",
        "motor náutico", "motor nautico", "motores náuticos", "motores nauticos",
        "motor diesel marítimo", "motor diesel maritimo",
        "motores diesel marítimos", "motores diesel maritimos",
        "motor dentro-fora", "motor dentro de borda",
        "motores dentro-fora", "motores dentro de borda",
        "motor de jet", "motor de jet ski",
        "motores de jet", "motores de jet ski",
        # ==== MANUTENÇÃO DE LANCHA ====
        # NOTA: "manutenção de motor" genérico FOI REMOVIDO (falso positivo com
        # motor de gerador, motor elétrico, motor industrial). Os motores
        # navais/popa/marítimos já são KW por si só — "Manutenção de motor
        # de popa" casa via "motor de popa".
        "manutenção de lancha", "manutencao de lancha",
        "manutenção de lanchas", "manutencao de lanchas",
        "reparo de motor de popa", "reparo de motor naval",
        "reparo de motor marítimo", "reparo de motor maritimo",
        "conserto de motor de popa", "conserto de motor naval",
        "revisão de motor de popa", "revisao de motor de popa",
        "revisão de motor naval", "revisao de motor naval",
        # ==== MANUTENÇÃO DE EMBARCAÇÃO (largo controlado — decisão usuário 2026-05-27) ====
        # "embarcação" é inequivocamente náutico (sem falso positivo como "motor").
        # Reintroduzido o serviço sobre embarcação; "manutenção de motor" genérico
        # SEGUE FORA (gerador/elétrico/industrial). Motor de popa/marítimo/naval
        # já casam por si só, cobrindo fornecimento/venda de motor náutico.
        "manutenção de embarcação", "manutencao de embarcacao",
        "manutenção de embarcações", "manutencao de embarcacoes",
        "reparo de embarcação", "reparo de embarcacao",
        "reparo de embarcações", "reparo de embarcacoes",
        "reparação de embarcação", "reparacao de embarcacao",
        "conserto de embarcação", "conserto de embarcacao",
        "conserto de embarcações", "conserto de embarcacoes",
        "revisão de embarcação", "revisao de embarcacao",
        "manutenção naval", "manutencao naval",
        "reparo naval", "reparos navais",
        # ==== AQUISIÇÃO/FORNECIMENTO DE EMBARCAÇÃO E MOTOR (decisão usuário 2026-05-28) ====
        # Sem isso, "Aquisição de Embarcação Militar Aruanã 29" cai no nicho
        # `aquisicao` ao invés de `nautico`. Reforça também aquisição de motor
        # náutico explicitamente (já cobre via qualificador motor de popa/naval).
        "aquisição de embarcação", "aquisicao de embarcacao",
        "aquisição de embarcações", "aquisicao de embarcacoes",
        "fornecimento de embarcação", "fornecimento de embarcacao",
        "fornecimento de embarcações", "fornecimento de embarcacoes",
        "compra de embarcação", "compra de embarcacao",
        "compra de embarcações", "compra de embarcacoes",
        "embarcação militar", "embarcacao militar",
        "embarcações militares", "embarcacoes militares",
        "fornecimento de motor de popa", "fornecimento de motor naval",
        "fornecimento de motor marítimo", "fornecimento de motor maritimo",
        "aquisição de motor de popa", "aquisicao de motor de popa",
        "aquisição de motor naval", "aquisicao de motor naval",
        # ==== MOTOR DE COMBUSTÃO PRINCIPAL E NAVIOS MARINHA (decisão 2026-05-28) ====
        # MCP = Motor de Combustão Principal de navio. Caso real: retifica de
        # conectoras do MCP do NOc Antares ficou em nicho=outros. Adicionado o
        # vocabulário Marinha: navios oceanográficos, patrulha, fragatas, corvetas.
        "motor de combustão principal", "motor de combustao principal",
        "motores de combustão principal", "motores de combustao principal",
        "motor de combustão auxiliar", "motor de combustao auxiliar",
        "motor de combustão naval", "motor de combustao naval",
        # NOMES DE NAVIO REMOVIDOS 2026-05-28: "fragata", "navio-patrulha",
        # "navio oceanográfico", "corveta", "corveta classe" pegavam editais
        # que SÓ MENCIONAVAM o navio como destino (ex: "Aquisição de gases
        # para a Fragata União" → não é náutico, é insumo industrial pra
        # consumo na fragata). Caso real: edital 5171 (gases pra maçarico).
        # Forma correta: usar verbo de trabalho naval (manutenção, reparo,
        # motor, propulsor, casco etc) — não nome de navio solto. Órgão
        # Marinha já é destacado via eh_marinha (prefixo visual).
        #
        # Formas QUALIFICADAS que mantêm "fragata/navio" mas exigem contexto
        # de trabalho naval — só casam quando combinadas:
        "manutenção da fragata", "manutencao da fragata",
        "manutenção do navio", "manutencao do navio",
        "reparo da fragata", "reparo do navio",
        "reparo de navio", "reparos de navio",
        # Submarinos da Marinha (decisão 2026-05-28 refinada após FP):
        # "submarino" solto pegava "Navio de Socorro Submarino Guillobel"
        # (tipo de navio que socorre submarinos, não é submarino) +
        # qualquer compra direcionada a ele (bolachas 5037, tintas 5157).
        # Solução: aceitar apenas formas qualificadas com referência à classe
        # ou serviço explícito em submarino. "Submarinos Classe X" é o padrão
        # Marinha pra referenciar submarinos reais (S-BR Classe Riachuelo etc.).
        "submarinos classe", "submarinos da classe",
        "submarino classe", "submarino da classe",
        "manutenção de submarino", "manutencao de submarino",
        "manutenção em submarino", "manutencao em submarino",
        "reparo de submarino", "reparo em submarino",
        "sobressalente para submarino", "sobressalente para submarinos",
        "sobressalentes para submarinos", "sobressalentes para submarino",
        "peça de submarino", "peca de submarino",
        "peças de submarino", "pecas de submarino",
        # Pintura/tinta naval (decisão 2026-05-28, caso 5157 — tintas para
        # Navio Submarino Guillobel). Tinta naval é uso específico náutico.
        "tinta naval", "tintas navais",
        "pintura naval", "pinturas navais",
        "tinta marítima", "tinta maritima",
        "tintas marítimas", "tintas maritimas",
        # Atracação/cabo naval (mantidos — são objetos navais inequívocos):
        "cabo de atracação", "cabo de atracacao",
        "cabo para atracação", "cabo para atracacao",
        "cabo naval", "reboque naval",
        "atracação naval", "atracacao naval",
        "atracação de embarcação", "atracacao de embarcacao",
        # ==== ÓLEOS / LUBRIFICANTES / FILTROS PARA MOTOR ====
        "óleo para motor de popa", "oleo para motor de popa",
        "óleo para motor naval", "oleo para motor naval",
        "óleo para motor marítimo", "oleo para motor maritimo",
        "óleo de motor de popa", "oleo de motor de popa",
        "óleo de motor naval", "oleo de motor naval",
        "lubrificante para motor de popa",
        "lubrificante para motor naval", "lubrificante para motor marítimo",
        "filtro de óleo naval", "filtro de oleo naval",
        "filtro de combustível naval", "filtro de combustivel naval",
    ],
}

# Empresa sugerida por nicho
EMPRESA_POR_NICHO = {
    "residuos": "sao_lourenco",
    "mdo_limpeza": "manutec",
    "seguranca": "miami",
    "admin": "blue",
    "obra": "manutec",
    "nautico": "powerboat",
    "outros": "manutec",
}


def _match_kw(kw: str, obj: str) -> bool:
    """Match com word boundaries — evita falsos positivos (ex: 'eta' em 'meta')."""
    # Escapa e usa \b pra palavras simples; se keyword ja tem espaco, substring basta
    if " " in kw:
        return kw in obj
    return re.search(rf"\b{re.escape(kw)}\b", obj) is not None


def _eh_aquisicao(obj: str) -> bool:
    """Detecta se o objeto e aquisicao de produto (nao servico)."""
    return any(re.search(p, obj) for p in PADROES_AQUISICAO)


def _eh_falso_seguranca(obj: str) -> bool:
    """Detecta contextos onde 'seguranca/vigilancia' NAO significa seguranca patrimonial."""
    return any(re.search(p, obj) for p in EXCLUSOES_SEGURANCA)


def _eh_falso_nautico(obj: str) -> bool:
    """Detecta contextos onde keyword náutica casou mas objeto NAO é náutico.
    Ex: 'Cestas básicas para Policlínica Naval' casa 'naval' mas é cesta básica.
    """
    return any(re.search(p, obj) for p in EXCLUSOES_NAUTICO)


def detectar_nicho(objeto: str) -> str:
    """Retorna nicho do edital baseado em keywords no objeto.

    Se for aquisicao de produto, retorna 'aquisicao' (fora do escopo de servicos).
    Filtra falsos positivos de seguranca (sanitaria, ambiental, do trabalho, etc).
    """
    obj = (objeto or "").lower()
    if not obj:
        return "outros"
    # Náutico tem prioridade — atende tanto aquisição quanto serviço.
    # (Powerboat: CNAE principal é varejista de embarcações/peças; aquisição é negócio core.)
    # Veta se objeto contém termos não-náuticos (ar-condicionado, cestas básicas, toner, etc).
    if not _eh_falso_nautico(obj):
        for kw in KEYWORDS_NICHO["nautico"]:
            if _match_kw(kw, obj):
                return "nautico"
    # Aquisicao de produto: nunca entra em nichos de servico
    if _eh_aquisicao(obj):
        return "aquisicao"
    for nicho in ("residuos", "seguranca", "admin", "mdo_limpeza", "obra"):
        for kw in KEYWORDS_NICHO[nicho]:
            if _match_kw(kw, obj):
                # Filtro anti-falso positivo para seguranca
                if nicho == "seguranca" and _eh_falso_seguranca(obj):
                    return "outros"
                return nicho
    return "outros"


def empresa_sugerida_por_nicho(nicho: str) -> str:
    return EMPRESA_POR_NICHO.get(nicho, "manutec")


@dataclass
class RotaTelegram:
    token: str
    chat_id: str


def rota_por_nicho(nicho: str) -> RotaTelegram | None:
    """Resolve bot token + chat_id para um nicho, com fallback para o geral.

    Env vars suportadas:
    - TELEGRAM_BOT_TOKEN_<NICHO_UPPER> (opcional)
    - TELEGRAM_CHAT_<NICHO_UPPER>      (opcional)
    - TELEGRAM_BOT_TOKEN               (geral, fallback)
    - TELEGRAM_CHAT_ID                 (geral, fallback)
    """
    key = nicho.upper()
    token = os.getenv(f"TELEGRAM_BOT_TOKEN_{key}") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv(f"TELEGRAM_CHAT_{key}") or os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return None
    return RotaTelegram(token=token, chat_id=chat)


def formatar_edital(edital: dict) -> str:
    """Formata edital no padrao canonico do projeto para Telegram."""
    from datetime import datetime

    def _dt(s):
        if not s:
            return "-"
        try:
            return datetime.fromisoformat(str(s)[:19]).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(s)[:16]

    modalidade = edital.get("modalidade") or "-"
    orgao = edital.get("orgao_nome") or "-"
    unidade = edital.get("unidade_nome") or edital.get("unidade") or ""
    uf = edital.get("uf") or "-"
    publicacao = _dt(edital.get("data_publicacao"))
    abertura = _dt(edital.get("data_abertura"))
    encerramento = _dt(edital.get("data_encerramento"))
    objeto_raw = (edital.get("objeto") or "").strip()
    objeto = objeto_raw[:200] + "..." if len(objeto_raw) > 200 else objeto_raw
    valor = edital.get("valor_estimado")
    sigiloso = edital.get("valor_sigiloso") or False
    link = edital.get("link_edital") or ""

    def _fmt_brl(v):
        """Formata valor em R$ padrão brasileiro (1.234.567,89)."""
        try:
            v = float(v)
            inteiro = int(v)
            centavos = round((v - inteiro) * 100)
            s = f"{inteiro:,}".replace(",", ".")
            return f"{s},{centavos:02d}"
        except Exception:
            return f"{v}"

    if sigiloso:
        valor_str = "Sigiloso"
    elif valor is None or valor == 0:
        valor_str = "Não informado"
    else:
        valor_str = f"R$ {_fmt_brl(valor)}"

    linhas = [
        f"📌 Modalidade: {modalidade}",
        f"🏛 Órgão: {orgao}",
    ]
    if unidade:
        linhas.append(f"🏢 Unidade: {unidade}")
    entidade = edital.get("entidade") or ""
    if entidade:
        linhas.append(f"🏢 Entidade: {entidade}")
    fonte = edital.get("fonte") or ""
    linhas += [
        f"📍 UF: {uf}",
        f"🗓 Publicação: {publicacao}",
        f"📨 Início propostas: {abertura}",
        f"⏰ Fim propostas: {encerramento}",
        f"🛠 Objeto: {objeto}",
        f"💰 Valor: {valor_str}",
    ]
    # Fonte: só mostra se for fonte externa (não PNCP)
    if fonte and fonte.lower() != "pncp":
        linhas.append(f"📡 Fonte: {fonte}")
    linhas.append(f"🔗 {link}")
    return "\n".join(linhas)


def enviar_documento_nicho(file_path: str, caption: str, nicho: str) -> bool:
    """Envia arquivo (PDF/XLSX) para o canal Telegram do nicho."""
    from pathlib import Path
    rota = rota_por_nicho(nicho)
    if not rota:
        log.warning(f"Sem rota Telegram para nicho '{nicho}'")
        return False
    try:
        import httpx
        p = Path(file_path)
        if not p.exists():
            log.warning(f"Arquivo nao encontrado: {file_path}")
            return False
        with open(p, "rb") as f:
            r = httpx.post(
                f"https://api.telegram.org/bot{rota.token}/sendDocument",
                data={"chat_id": rota.chat_id, "caption": caption[:1024]},
                files={"document": (p.name, f, "application/octet-stream")},
                timeout=60,
            )
        if r.status_code == 200:
            return True
        log.warning(f"Telegram sendDocument {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log.error(f"Telegram documento erro: {e}")
    return False


def baixar_e_enviar_edital(url_edital: str, nome: str, caption: str, nicho: str) -> bool:
    """Baixa PDF do edital e envia pro canal Telegram."""
    if not url_edital:
        return False
    try:
        import httpx
        import tempfile
        from pathlib import Path
        with httpx.Client(timeout=60, follow_redirects=True) as cli:
            r = cli.get(url_edital, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                log.warning(f"Download edital {r.status_code}: {url_edital[:80]}")
                return False
            ext = ".pdf"
            ct = r.headers.get("content-type", "")
            if "spreadsheet" in ct or "excel" in ct:
                ext = ".xlsx"
            elif "zip" in ct:
                ext = ".zip"
            tmp = Path(tempfile.mktemp(suffix=ext, prefix=f"edital_{nome}_"))
            tmp.write_bytes(r.content)
            ok = enviar_documento_nicho(str(tmp), caption, nicho)
            tmp.unlink(missing_ok=True)
            return ok
    except Exception as e:
        log.error(f"Erro baixar/enviar edital: {e}")
        return False


def enviar_para_nicho(msg: str, nicho: str, parse_mode: str = "HTML") -> bool:
    """Envia mensagem para o canal Telegram do nicho (ou geral se nao configurado)."""
    rota = rota_por_nicho(nicho)
    if not rota:
        log.warning(f"Sem rota Telegram para nicho '{nicho}'")
        return False
    try:
        import httpx
        payload = {"chat_id": rota.chat_id, "text": msg}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        r = httpx.post(
            f"https://api.telegram.org/bot{rota.token}/sendMessage",
            json=payload,
            timeout=15,
        )
        if r.status_code == 200:
            return True
        log.warning(f"Telegram {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log.error(f"Telegram erro: {e}")
    return False
