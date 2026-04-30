"""Classificador de nicho + roteador de notificacoes Telegram.

Nichos: residuos, mdo_limpeza, seguranca, admin, obra, outros.
Cada nicho pode ter canal Telegram dedicado via env TELEGRAM_CHAT_<NICHO>.
"""
import logging
import os
import re
from dataclasses import dataclass

log = logging.getLogger("nichos")

NICHOS = ("residuos", "mdo_limpeza", "seguranca", "admin", "obra", "aquisicao", "outros")

# Padroes que indicam AQUISICAO de produto (nao servico) — excluir dos nichos de servico
PADROES_AQUISICAO = [
    r"^aquisi[cç][aã]o\b",
    r"^fornecimento\b",
    r"^compra\b",
    r"\baquisi[cç][aã]o de (materiais|equipamentos|produtos|g[eê]neros|m[oó]veis|insumos|tubos|conjuntos|condicionadores)\b",
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
        "obra", "construção", "construcao", "reforma",
        "ampliação", "ampliacao", "pavimentação", "pavimentacao",
        "drenagem", "engenharia civil", "edificação",
        "edificacao", "urbanização", "urbanizacao",
        "infraestrutura", "impermeabilização", "impermeabilizacao",
    ],
}

# Empresa sugerida por nicho
EMPRESA_POR_NICHO = {
    "residuos": "sao_lourenco",
    "mdo_limpeza": "manutec",
    "seguranca": "miami",
    "admin": "blue",
    "obra": "manutec",
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


def detectar_nicho(objeto: str) -> str:
    """Retorna nicho do edital baseado em keywords no objeto.

    Se for aquisicao de produto, retorna 'aquisicao' (fora do escopo de servicos).
    Filtra falsos positivos de seguranca (sanitaria, ambiental, do trabalho, etc).
    """
    obj = (objeto or "").lower()
    if not obj:
        return "outros"
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
