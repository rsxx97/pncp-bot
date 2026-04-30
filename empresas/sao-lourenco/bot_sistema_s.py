"""Bot Sistema S — scraper de licitacoes fora do PNCP.

Fontes: Licitacoes-e (BB), Portal de Compras Publicas, SEBRAE.
Cobre: SESC, SENAC, SENAI, SESI, SEBRAE, Petrobras, autarquias.

Zero API. Dedup em data/skills/sistema_s_sent.json.
Roda a cada 2h via Task Scheduler.
"""
import argparse
import hashlib
import json
import logging
import re
import sqlite3
import sys
import time
from datetime import datetime, date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "licitacoes-ai"))
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / "licitacoes-ai" / ".env", override=True)

from config.settings import DB_PATH
from shared.nichos import detectar_nicho, formatar_edital, enviar_para_nicho, rota_por_nicho

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_sistema_s")

BASE = Path(__file__).parent.parent
SENT_FILE = BASE / "data" / "skills" / "sistema_s_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

UFS_INTERESSE = ["BR"]  # nivel Brasil (todos estados)
KEYWORDS_RESIDUOS = [
    # 20 keywords base (Sao Lourenco)
    "resíduos", "residuos", "rejeito", "rejeitos", "reciclagem",
    "água oleosa", "agua oleosa", "borra oleosa",
    "efluente", "efluentes",
    "lâmpada fluorescente", "lampada fluorescente",
    "pcb", "ascarel",
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
    "resíduo hospitalar", "residuo hospitalar",
    "entulho", "chorume",
    "produtos perigosos",
    "slop", "slops",
    "lama de perfuração", "lama de perfuracao",
    "logística reversa", "logistica reversa",
    # +7 moderados
    "licenciamento ambiental", "passivo ambiental",
    "remediação", "remediacao",
    "solo contaminado", "sucata",
    "desativação de tanque", "desativacao de tanque",
    # locação de caçamba + destinação
    "locação de caçamba", "locacao de cacamba",
    "caçamba estacionária", "cacamba estacionaria",
    "caçamba roll", "cacamba roll",
    "roll-on", "roll-off",
    "transporte e destinação", "transporte e destinacao",
    "remoção de entulho", "remocao de entulho",
    "bota-fora", "bota fora",
]
KEYWORDS_OBRA = [
    "obra", "reforma", "construção", "construcao", "pavimentação",
    "engenharia", "calçada", "calcada", "passeio",
]
KEYWORDS_SERVICO = [
    "limpeza", "vigilância", "vigilancia", "portaria", "manutenção",
    "manutencao", "terceirização", "terceirizacao",
]

# ═══ NICHOS ADICIONADOS (Petrobras: transporte + carga perigosa + variados) ═══
KEYWORDS_TRANSPORTE = [
    "transporte de pessoal", "transporte de funcionários",
    "transporte terrestre", "transporte rodoviário", "transporte rodoviario",
    "transporte marítimo", "transporte maritimo",
    "transporte de carga", "fretamento",
    "transporte logístico", "transporte logistico",
    "locação de veículo", "locacao de veiculo",
    "locação de veículos", "locacao de veiculos",
]
KEYWORDS_CARGA_PERIGOSA = [
    "transporte de carga perigosa",
    "transporte de produtos perigosos",
    "transporte de resíduos perigosos",
    "transporte de produtos químicos", "transporte de produtos quimicos",
    "transporte de combustíveis", "transporte de combustiveis",
    "transporte de inflamáveis", "transporte de inflamaveis",
    "MOPP", "mopp obrigatório",
    "classe de risco", "onu ",
    "produto inflamável", "produto inflamavel",
    "produtos radioativos",
    "resíduo classe i", "residuo classe i",
]
KEYWORDS_VARIADOS = [
    "serviços diversos", "servicos diversos",
    "serviços operacionais", "servicos operacionais",
    "apoio logístico", "apoio logistico",
    "manutenção offshore", "manutencao offshore",
    "operação integrada", "operacao integrada",
    "serviços especializados", "servicos especializados",
    "serviços continuados", "servicos continuados",
]


def _load_sent() -> set:
    if SENT_FILE.exists():
        return set(json.loads(SENT_FILE.read_text(encoding="utf-8")))
    return set()


def _save_sent(s: set):
    SENT_FILE.write_text(json.dumps(sorted(s)), encoding="utf-8")


def _hash_id(fonte: str, titulo: str, orgao: str) -> str:
    """Gera ID unico a partir de fonte+titulo+orgao."""
    raw = f"{fonte}|{titulo}|{orgao}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _match_interesse(texto: str) -> bool:
    """Verifica se o texto contem keywords de interesse (todos nichos)."""
    t = texto.lower()
    all_kw = (KEYWORDS_RESIDUOS + KEYWORDS_OBRA + KEYWORDS_SERVICO
              + KEYWORDS_TRANSPORTE + KEYWORDS_CARGA_PERIGOSA + KEYWORDS_VARIADOS)
    return any(k in t for k in all_kw)


def _classificar_nicho(texto: str) -> str:
    """Classifica em: residuos / transporte / carga_perigosa / variados / obra / servico."""
    t = texto.lower()
    if any(k in t for k in KEYWORDS_CARGA_PERIGOSA):
        return "carga_perigosa"
    if any(k in t for k in KEYWORDS_RESIDUOS):
        return "residuos"
    if any(k in t for k in KEYWORDS_TRANSPORTE):
        return "transporte"
    if any(k in t for k in KEYWORDS_VARIADOS):
        return "variados"
    if any(k in t for k in KEYWORDS_OBRA):
        return "obra"
    if any(k in t for k in KEYWORDS_SERVICO):
        return "servico"
    return "geral"


def _formatar_sistema_s(item: dict) -> str:
    """Formata item no padrao IDENTICO ao PNCP. Só mostra campos com dado real."""
    import re

    orgao = item.get("orgao") or "-"
    uf = item.get("uf") or "RJ"
    objeto_raw = (item.get("objeto") or "-").strip()
    fonte = item.get("fonte") or "-"
    link = item.get("link") or ""
    numero = item.get("numero") or ""
    encerramento = item.get("encerramento") or ""
    publicacao = item.get("publicacao") or ""
    abertura = item.get("abertura") or ""
    modalidade = item.get("modalidade") or ""
    entidade = item.get("entidade") or ""
    valor_raw = item.get("valor") or ""

    # Extrai dados do texto do objeto se nao vieram separados
    if not encerramento:
        m = re.search(r'(\d{2}/\d{2}/\d{4}\s*\d{0,2}:?\d{0,2})', objeto_raw)
        if m:
            encerramento = m.group(1).strip()

    if not numero:
        m = re.search(r'(\d{2,}/\d{4})', objeto_raw)
        if m:
            numero = m.group(1)

    if not modalidade:
        for kw, mod in [('pregão', 'Pregão Eletrônico'), ('pregao', 'Pregão Eletrônico'),
                        ('concorrência', 'Concorrência'), ('concorrencia', 'Concorrência'),
                        ('dispensa', 'Dispensa'), ('credenciamento', 'Credenciamento'),
                        ('lre', 'LRE')]:
            if kw in objeto_raw.lower():
                modalidade = mod
                break
        if not modalidade:
            modalidade = "Licitação"

    if not valor_raw:
        m = re.search(r'R\$\s*([\d.,]+)', objeto_raw)
        if m:
            valor_raw = m.group(0)

    # Limpa objeto
    objeto = objeto_raw[:250] + "..." if len(objeto_raw) > 250 else objeto_raw

    # Monta mensagem — formato IDENTICO ao PNCP
    linhas = [
        f"📌 Modalidade: {modalidade}",
        f"🏛 Órgão: {orgao}",
    ]
    if entidade:
        linhas.append(f"🏢 Entidade: {entidade}")
    linhas.append(f"📍 UF: {uf}")
    if publicacao:
        linhas.append(f"🗓 Publicação: {publicacao}")
    if abertura:
        linhas.append(f"📨 Início propostas: {abertura}")
    if encerramento:
        linhas.append(f"⏰ Fim propostas: {encerramento}")
    linhas.append(f"🛠 Objeto: {objeto}")
    if valor_raw:
        try:
            v = float(str(valor_raw).replace("R$", "").replace(".", "").replace(",", ".").strip())
            linhas.append(f"💰 Valor: R$ {v:,.2f}")
        except Exception:
            linhas.append(f"💰 Valor: {valor_raw}")
    linhas.append(f"📡 Fonte: {fonte}")
    if link:
        linhas.append(f"🔗 {link}")
    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════
# FONTE 1: Portal de Compras Publicas
# ═══════════════════════════════════════════════════════════════
def scrape_portal_compras(ufs: list[str] = None) -> list[dict]:
    """Scraping Portal de Compras Publicas — busca por UF + status aberto."""
    if ufs is None:
        ufs = UFS_INTERESSE
    resultados = []
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as cli:
        for uf in ufs:
            try:
                url = f"https://www.portaldecompraspublicas.com.br/processos?uf={uf}&status=recebendo_propostas"
                r = cli.get(url)
                if r.status_code != 200:
                    log.warning(f"Portal Compras {uf}: HTTP {r.status_code}")
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                cards = soup.select(".card, .processo-item, tr, .licitacao-item, article")
                for card in cards:
                    texto = card.get_text(" ", strip=True)
                    if not _match_interesse(texto):
                        continue
                    link_tag = card.find("a", href=True)
                    link = ""
                    if link_tag:
                        href = link_tag["href"]
                        if not href.startswith("http"):
                            href = f"https://www.portaldecompraspublicas.com.br{href}"
                        link = href
                    resultados.append({
                        "fonte": "Portal Compras Públicas",
                        "orgao": texto[:80],
                        "objeto": texto[:250],
                        "uf": uf,
                        "link": link,
                    })
                log.info(f"Portal Compras {uf}: {len(cards)} cards, {len([r for r in resultados if r['uf']==uf])} relevantes")
            except Exception as e:
                log.warning(f"Portal Compras {uf}: {e}")
    return resultados


# ═══════════════════════════════════════════════════════════════
# FONTE 2: Licitacoes-e (Banco do Brasil)
# ═══════════════════════════════════════════════════════════════
def scrape_licitacoes_e(ufs: list[str] = None) -> list[dict]:
    """Scraping Licitacoes-e (BB) — SESC, SENAC, SENAI, SESI, Petrobras."""
    if ufs is None:
        ufs = UFS_INTERESSE
    resultados = []
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as cli:
        for uf in ufs:
            try:
                # Tenta endpoint de busca publica
                url = "https://licitacoes-e2.bb.com.br/aop/pesquisar-licitacao.aop"
                params = {
                    "sgUf": uf,
                    "situacao": "AB",  # Abertas
                    "pagina": 1,
                    "tamanhoPagina": 50,
                }
                r = cli.get(url, params=params)
                if r.status_code == 200:
                    # Tenta JSON
                    try:
                        data = r.json()
                        items = data if isinstance(data, list) else data.get("licitacoes", data.get("data", []))
                        for it in items:
                            obj = it.get("objeto") or it.get("descricao") or it.get("titulo") or ""
                            if not _match_interesse(obj):
                                continue
                            resultados.append({
                                "fonte": "Licitações-e (BB)",
                                "orgao": it.get("orgao", it.get("entidade", "")),
                                "entidade": it.get("entidade", ""),
                                "objeto": obj[:250],
                                "uf": uf,
                                "valor": it.get("valor", ""),
                                "abertura": it.get("dataAbertura", ""),
                                "encerramento": it.get("dataEncerramento", ""),
                                "modalidade": it.get("modalidade", ""),
                                "link": it.get("link", f"https://licitacoes-e.com.br"),
                            })
                    except Exception:
                        # HTML fallback
                        soup = BeautifulSoup(r.text, "html.parser")
                        rows = soup.select("tr, .licitacao, article, .card")
                        for row in rows:
                            texto = row.get_text(" ", strip=True)
                            if _match_interesse(texto):
                                link_tag = row.find("a", href=True)
                                resultados.append({
                                    "fonte": "Licitações-e (BB)",
                                    "objeto": texto[:250],
                                    "uf": uf,
                                    "link": link_tag["href"] if link_tag else "",
                                })
                    log.info(f"Licitações-e {uf}: {len([r for r in resultados if r['uf']==uf])} relevantes")
                else:
                    # Alternativa: busca via URL publica
                    alt_url = f"https://licitacoes-e2.bb.com.br/aop/licitacao/listaTodasLicitacoes.aop?sgUf={uf}"
                    r2 = cli.get(alt_url)
                    if r2.status_code == 200:
                        soup = BeautifulSoup(r2.text, "html.parser")
                        for row in soup.select("tr"):
                            texto = row.get_text(" ", strip=True)
                            if _match_interesse(texto):
                                resultados.append({
                                    "fonte": "Licitações-e (BB)",
                                    "objeto": texto[:250],
                                    "uf": uf,
                                })
                    log.info(f"Licitações-e {uf} (alt): status {r.status_code}/{r2.status_code if 'r2' in dir() else '?'}")
            except Exception as e:
                log.warning(f"Licitações-e {uf}: {e}")
    return resultados


# ═══════════════════════════════════════════════════════════════
# FONTE 3: SEBRAE
# ═══════════════════════════════════════════════════════════════
def scrape_sebrae() -> list[dict]:
    """Scraping SEBRAE nacional."""
    resultados = []
    urls = [
        "https://sebfrn.nfrn.com.br/licitacoes",
        "https://www.sebrae.com.br/sites/PortalSebrae/licitacoes",
        "https://www.sebraerj.com.br/licitacoes",
        "https://www.sebrae-sc.com.br/licitacoes",
    ]
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as cli:
        for url in urls:
            try:
                r = cli.get(url)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                for link_tag in soup.find_all("a", href=True):
                    texto = link_tag.get_text(" ", strip=True)
                    if len(texto) > 20 and _match_interesse(texto):
                        href = link_tag["href"]
                        if not href.startswith("http"):
                            href = url.rsplit("/", 1)[0] + "/" + href
                        resultados.append({
                            "fonte": "SEBRAE",
                            "orgao": "SEBRAE",
                            "objeto": texto[:250],
                            "link": href,
                        })
                log.info(f"SEBRAE {url}: {r.status_code}")
            except Exception as e:
                log.warning(f"SEBRAE {url}: {e}")
    return resultados


# ═══════════════════════════════════════════════════════════════
# FONTE 4: SESC/SENAC estaduais
# ═══════════════════════════════════════════════════════════════
# URLs institucionais (nao sao licitacoes)
_URL_BLACKLIST = (
    "/regras-de-contratacao", "/sobre-", "/quem-somos", "/nossa-historia",
    "/institucional", "/imprensa", "/midia", "/faq", "/perguntas-frequentes",
    "/politica", "/politicas", "/sustentabilidade/", "/contato", "/privacidade",
    "/compliance", "/governanca", "/relacionamento", "/canal-de-etica",
    "/como-", "/o-que-e", "/saiba-", "/conheca-", "/entenda-",
)
# Titulos de paginas institucionais (nao licitacoes)
_TITULO_BLACKLIST_PREFIXOS = (
    "as formas", "o que é", "o que e", "como ", "sobre ", "nossa ",
    "perguntas", "saiba ", "conheça", "conheca", "quem somos",
    "entenda ", "veja como", "política ", "politica ",
)


def _parece_institucional(titulo: str, href: str) -> bool:
    """True se URL ou titulo sao claramente de pagina institucional, nao licitacao."""
    href_low = (href or "").lower()
    if any(p in href_low for p in _URL_BLACKLIST):
        return True
    tl = titulo.lower().strip()
    if any(tl.startswith(p) for p in _TITULO_BLACKLIST_PREFIXOS):
        return True
    return False


# Empresas/órgãos com UF fixa conhecida — usado pra rejeitar editais não-RJ vazando em portais multi-UF (ex: AEGEA mostra CORSAN/RS).
_ENTIDADES_UF_FIXA = {
    "CORSAN": "RS", "SABESP": "SP", "COPASA": "MG", "CAESB": "DF",
    "COMPESA": "PE", "CAGECE": "CE", "EMBASA": "BA", "SANEAGO": "GO",
    "CASAN": "SC", "COSANPA": "PA", "SANEPAR": "PR", "DAEV": "SP",
}


def _detectar_uf_texto(texto: str) -> str | None:
    """Detecta UF do texto. Prioridade: entidades conhecidas > regex \\bUF\\b. None se indetectável."""
    import re
    upper = texto.upper()
    for ent, uf in _ENTIDADES_UF_FIXA.items():
        if ent in upper:
            return uf
    m = re.search(r'\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SE|SP|TO)\b', texto)
    if m:
        return m.group(1)
    return None


def _pw_extrair_links(page, nome: str, uf: str) -> list[dict]:
    """Extrai licitacoes reais (com numero/data/link) da pagina. Ignora texto informativo."""
    import re
    resultados = []
    for el in page.query_selector_all("tr, li, article, .card"):
        try:
            txt = (el.inner_text() or "").strip()
            if len(txt) < 40 or len(txt) > 600:
                continue  # titulos muito curtos sao menus; muito longos sao blocos mistos
            txt_lower = txt.lower()
            # Precisa ter keyword de residuos
            if not any(k in txt_lower for k in KEYWORDS_RESIDUOS):
                continue
            # Link primeiro — descarta paginas institucionais antes de qualquer coisa
            href = ""
            link_tag = el.query_selector("a")
            if link_tag:
                href = link_tag.get_attribute("href") or ""
            if _parece_institucional(txt, href):
                continue
            # Indicadores de licitacao real
            tem_numero = bool(re.search(r'\d{2,}/\d{4}|\d{4,}', txt))
            tem_data = bool(re.search(r'\d{2}/\d{2}/\d{4}', txt))
            tem_valor = bool(re.search(r'r\$\s*[\d.,]+', txt_lower))
            tem_modalidade = any(w in txt_lower for w in [
                'edital', 'pregão', 'pregao', 'processo licitatório', 'processo licitatorio',
                'licitação nº', 'licitacao n', 'concorrência', 'concorrencia',
                'dispensa de licitação', 'dispensa de licitacao',
                'chamamento público', 'chamamento publico', 'tomada de preço',
            ])
            # EXIGE pelo menos 2 sinais — evita disparar em menu/institucional com uma palavra solta
            sinais = sum([tem_numero, tem_data, tem_valor, tem_modalidade])
            if sinais < 2:
                continue
            # Link tem que ser de edital/licitacao — se href aponta para / ou home, descarta
            if href and not href.startswith("http"):
                pass  # relativo, ok
            if href and href.rstrip("/") in ("", "/", "https://canalfornecedor.petrobras.com.br"):
                href = ""
            data_match = re.search(r'(\d{2}/\d{2}/\d{4})', txt)
            num_match = re.search(r'(\d{2,}/\d{4})', txt)
            uf_real = _detectar_uf_texto(txt) or uf
            resultados.append({
                "fonte": nome,
                "orgao": nome,
                "objeto": txt[:250],
                "uf": uf_real,
                "link": href if href.startswith("http") else "",
                "encerramento": data_match.group(1) if data_match else "",
                "numero": num_match.group(1) if num_match else "",
            })
        except Exception:
            continue
    return resultados


def _le_screenshot(page, nome: str):
    """Salva screenshot do Licitacoes-e para debug."""
    try:
        ts = datetime.now().strftime("%H%M%S")
        path = BASE / "data" / "screenshots" / f"le_{nome}_{ts}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=True)
        log.info(f"Screenshot: {path.name}")
    except Exception as e:
        log.warning(f"Screenshot falhou: {e}")


def _le_navegar(page, max_tentativas: int = 5) -> bool:
    """Navega ate o formulario do Licitacoes-e, retentando ate carregar."""
    url = "https://www.licitacoes-e.com.br/aop/pesquisar-licitacao.aop?opcao=preencherPesquisar"
    for t in range(max_tentativas):
        try:
            log.info(f"Licitacoes-e navegando (tentativa {t+1}/{max_tentativas})...")
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            # Verifica se carregou o formulario
            form_ok = page.query_selector("input[value='pesquisar'], input[value='Pesquisar']")
            if form_ok:
                _le_screenshot(page, f"form_ok_t{t+1}")
                log.info(f"Formulario carregado na tentativa {t+1}")
                return True
            _le_screenshot(page, f"sem_form_t{t+1}")
            log.warning(f"Pagina carregou mas sem formulario (tentativa {t+1})")
        except Exception as e:
            log.warning(f"Navegacao falhou (tentativa {t+1}): {e}")
        page.wait_for_timeout(3000)
    return False


def _le_selecionar_situacao(page, valor_texto: str) -> bool:
    """Seleciona situacao da licitacao pelo texto visivel da option."""
    # JSF renderiza selects ocultos — vai direto pro JS que funciona
    try:
        ok = page.evaluate(f'''() => {{
            let selects = document.querySelectorAll('select');
            for (let sel of selects) {{
                for (let opt of sel.options) {{
                    if (opt.text.toLowerCase().includes("{valor_texto.lower()}")) {{
                        sel.value = opt.value;
                        sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return true;
                    }}
                }}
            }}
            return false;
        }}''')
        if ok:
            page.wait_for_timeout(1000)
            log.info(f"Situacao selecionada via JS: {valor_texto}")
            return True
        log.warning(f"Option '{valor_texto}' nao encontrada nos selects")
        return False
    except Exception as e:
        log.warning(f"Falha ao selecionar situacao '{valor_texto}': {e}")
        return False


def _le_resolver_captcha(page, ocr) -> str:
    """Encontra imagem captcha, faz OCR, preenche campo. Retorna texto lido."""
    # Encontra imagem do captcha (imagem grande perto do fim da pagina)
    captcha_img = None
    for img in page.query_selector_all("img"):
        try:
            box = img.bounding_box()
            if not box:
                continue
            # Captcha: imagem com largura razoavel, na metade inferior
            if box["width"] > 80 and box["height"] > 20:
                src = img.get_attribute("src") or ""
                # Captcha tem src com "captcha" ou "imagem" ou esta perto do botao pesquisar
                if "captcha" in src.lower() or "imagem" in src.lower() or box["y"] > 400:
                    captcha_img = img
        except Exception:
            continue

    if not captcha_img:
        log.warning("Imagem captcha nao encontrada")
        return ""

    # Screenshot do captcha + OCR
    captcha_bytes = captcha_img.screenshot()
    captcha_text = ocr.classification(captcha_bytes).strip()

    # Limita a 5 caracteres (regra do site)
    captcha_text = captcha_text[:5]

    log.info(f"Captcha OCR: '{captcha_text}'")

    # Preenche campo do captcha — acha ultimo input text visivel (perto do captcha)
    preenchido = False
    inputs = page.query_selector_all('input[type="text"]')
    captcha_input = None
    for inp in reversed(inputs):
        try:
            box = inp.bounding_box()
            if box and box["y"] > 400 and box["width"] > 40:
                captcha_input = inp
                break
        except Exception:
            continue

    if captcha_input:
        try:
            captcha_input.fill("")
            captcha_input.fill(captcha_text)
            preenchido = True
        except Exception:
            # Fallback JS
            page.evaluate(f'''() => {{
                let inputs = document.querySelectorAll('input[type="text"]');
                let last; for(let i of inputs) {{ let r=i.getBoundingClientRect(); if(r.top>400 && r.width>40) last=i; }}
                if(last) {{ last.value="{captcha_text}"; last.dispatchEvent(new Event("input", {{bubbles:true}})); }}
            }}''')
            preenchido = True

    if not preenchido:
        log.warning("Campo captcha nao encontrado para preencher")

    return captcha_text


def scrape_licitacoes_e_pw(page) -> list[dict]:
    """Licitacoes-e (BB) via Playwright — preenche form + OCR captcha.
    Robusto: screenshots em cada etapa, retry ate conseguir."""
    resultados = []
    try:
        import ddddocr
        ocr = ddddocr.DdddOcr(show_ad=False)
    except Exception:
        log.warning("ddddocr nao disponivel, pulando Licitacoes-e")
        return []

    # Situacoes abertas e seus textos no select
    situacoes = [
        "Publicada",
        "Acolhimento de propostas",
        "Abertura de propostas",
        "Em disputa",
    ]
    termos = [
        # Resíduos
        "residuos", "reciclagem", "cacamba", "coleta", "aterro", "destinacao",
        # Transporte + Petrobras
        "transporte", "carga perigosa", "mopp",
        "offshore", "produtos perigosos",
    ]

    for sit_texto in situacoes:
        for termo in termos:
            pesquisa_ok = False
            for tentativa in range(6):  # ate 6 tentativas por combo (captcha falha ~50%)
                try:
                    # 1. NAVEGAR ate o formulario
                    if not _le_navegar(page):
                        log.error("Licitacoes-e: impossivel carregar formulario apos retries")
                        break

                    # 2. SELECIONAR SITUACAO
                    if not _le_selecionar_situacao(page, sit_texto):
                        _le_screenshot(page, f"sit_falhou_{sit_texto[:10]}")
                        break  # pula essa situacao

                    # 3. PREENCHER MERCADORIA
                    merc_input = page.query_selector('input[name*="ercadoria"], input[name*="mercadoria"]')
                    if not merc_input:
                        # Fallback: acha por posicao
                        merc_input = page.evaluate('''() => {
                            let inputs = document.querySelectorAll('input[type="text"]');
                            for (let inp of inputs) {
                                let rect = inp.getBoundingClientRect();
                                if (rect.top > 300 && rect.top < 500 && rect.width > 150) {
                                    inp.value = "";
                                    return true;
                                }
                            }
                            return false;
                        }''')
                    if merc_input and hasattr(merc_input, 'fill'):
                        merc_input.fill(termo)
                    else:
                        page.evaluate(f'''() => {{
                            let inputs = document.querySelectorAll('input[type="text"]');
                            for (let inp of inputs) {{
                                let rect = inp.getBoundingClientRect();
                                if (rect.top > 300 && rect.top < 500 && rect.width > 150) {{
                                    inp.value = "{termo}";
                                    inp.dispatchEvent(new Event("input", {{bubbles: true}}));
                                    return true;
                                }}
                            }}
                            return false;
                        }}''')

                    _le_screenshot(page, f"pre_captcha_{sit_texto[:5]}_{termo}_t{tentativa+1}")

                    # 4. RESOLVER CAPTCHA
                    captcha_text = _le_resolver_captcha(page, ocr)
                    if not captcha_text:
                        _le_screenshot(page, f"sem_captcha_t{tentativa+1}")
                        continue

                    _le_screenshot(page, f"pre_submit_{sit_texto[:5]}_{termo}_t{tentativa+1}")

                    # 5. SUBMIT
                    btn = page.query_selector("input[value='pesquisar'], input[value='Pesquisar']")
                    if btn:
                        btn.click()
                    else:
                        page.evaluate('''() => {
                            let btn = document.querySelector("input[value='pesquisar']") ||
                                      document.querySelector("input[value='Pesquisar']");
                            if (btn) btn.form.submit();
                        }''')
                    page.wait_for_timeout(8000)

                    _le_screenshot(page, f"pos_submit_{sit_texto[:5]}_{termo}_t{tentativa+1}")

                    # 6. AVALIAR RESULTADO
                    body = page.inner_text("body").lower()

                    # Captcha errado — retry (site mostra "Resposta Incorreta!")
                    if "incorret" in body or "invalid" in body or "inválid" in body:
                        log.info(f"Captcha errado (tentativa {tentativa+1}), retentando...")
                        continue

                    # Erro de validacao (situacao nao selecionada)
                    if "selecione a situa" in body:
                        log.warning(f"Situacao nao foi selecionada, retentando...")
                        continue

                    # Mais de 5 chars no captcha
                    if "more than 5" in body or "mais de 5" in body:
                        log.info(f"Captcha >5 chars, retentando...")
                        continue

                    # Erros genericos de validacao
                    if "corrigir os seguintes erros" in body:
                        log.warning(f"Erro de validacao (tentativa {tentativa+1}), retentando...")
                        continue

                    # Sem resultados — ok, proximo combo
                    if "não encontrada" in body or "nao encontrada" in body:
                        log.info(f"Sem resultados: sit={sit_texto}, termo={termo}")
                        pesquisa_ok = True
                        break

                    # TEM RESULTADOS — extrair
                    log.info(f"Resultados encontrados: sit={sit_texto}, termo={termo}")
                    _le_screenshot(page, f"resultado_{sit_texto[:5]}_{termo}")

                    # Tabela do BB: colunas = (#), Comprador, Licitacao, Descricao
                    for row in page.query_selector_all("tr"):
                        txt = (row.inner_text() or "").strip()
                        if len(txt) < 30:
                            continue
                        txt_l = txt.lower()
                        if not any(k in txt_l for k in KEYWORDS_RESIDUOS):
                            continue
                        cells = row.query_selector_all("td")
                        if len(cells) >= 3:
                            # Extrai dados estruturados
                            comprador = cells[1].inner_text().strip() if len(cells) > 1 else ""
                            num_licitacao = cells[2].inner_text().strip() if len(cells) > 2 else ""
                            descricao = cells[3].inner_text().strip() if len(cells) > 3 else txt
                            # Extrai UF da descricao (padrao "UF: XX")
                            import re as _re
                            uf_match = _re.search(r'UF:\s*([A-Z]{2})', descricao)
                            uf_item = uf_match.group(1) if uf_match else "BR"
                            # Extrai link da licitacao
                            link_tag = row.query_selector("a")
                            href = link_tag.get_attribute("href") if link_tag else ""
                            if href and not href.startswith("http"):
                                href = f"https://www.licitacoes-e.com.br{href}"
                            # Extrai numero edital e modalidade
                            edital_match = _re.search(r'Edital\s*:\s*(\S+)', descricao)
                            mod_match = _re.search(r'Modalidade/tipo:\s*(\w+)', descricao)
                            resultados.append({
                                "fonte": "Licitações-e (BB)",
                                "orgao": comprador[:80] or "Sistema S / BB",
                                "objeto": descricao[:250] or txt[:250],
                                "uf": uf_item,
                                "link": href,
                                "numero": num_licitacao,
                                "modalidade": mod_match.group(1) if mod_match else "Pregão",
                                "encerramento": edital_match.group(1) if edital_match else "",
                            })
                            log.info(f"  BB encontrou: {comprador[:40]} | Lic {num_licitacao} | UF {uf_item}")
                        else:
                            # Fallback: sem estrutura de tabela
                            link_tag = row.query_selector("a")
                            href = link_tag.get_attribute("href") if link_tag else ""
                            if href and not href.startswith("http"):
                                href = f"https://www.licitacoes-e.com.br{href}"
                            resultados.append({
                                "fonte": "Licitações-e (BB)",
                                "orgao": "Sistema S / BB",
                                "objeto": txt[:250],
                                "uf": "BR",
                                "link": href,
                            })
                    pesquisa_ok = True
                    break

                except Exception as e:
                    log.warning(f"BB sit={sit_texto} termo={termo} t={tentativa+1}: {e}")
                    _le_screenshot(page, f"erro_{sit_texto[:5]}_{termo}_t{tentativa+1}")
                    continue  # retry em vez de break

            if not pesquisa_ok:
                log.warning(f"Esgotou tentativas: sit={sit_texto}, termo={termo}")

    log.info(f"Licitações-e: {len(resultados)} residuos total")
    return resultados


def scrape_sebrae_pw(page) -> list[dict]:
    """SEBRAE via Playwright — busca em varios portais estaduais."""
    resultados = []
    urls_sebrae = [
        ("SEBRAE-RJ", "https://www.sebraerj.com.br/transparencia/licitacoes", "RJ"),
        ("SEBRAE-SC", "https://www.sebrae-sc.com.br/transparencia/licitacoes", "SC"),
        ("SEBRAE-Nacional", "https://www.sebrae.com.br/sites/PortalSebrae/transparencia/licitacoes", "BR"),
        ("SEBRAE-RJ-2", "https://sebraerj.com.br/transparencia", "RJ"),
    ]
    for nome, url, uf in urls_sebrae:
        try:
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            r = _pw_extrair_links(page, nome, uf)
            resultados.extend(r)
            log.info(f"{nome}: {len(r)} relevantes")
        except Exception as e:
            log.warning(f"{nome}: {e}")
    return resultados


def scrape_petrobras_pw(page) -> list[dict]:
    """Petrobras Canal Fornecedor via Playwright."""
    resultados = []
    # So raspa endpoints de oportunidades. Home e paginas institucionais sao blacklisted.
    urls = [
        ("Petrobras", "https://canalfornecedor.petrobras.com.br/oportunidades", "RJ"),
    ]
    for nome, url, uf in urls:
        try:
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            r = _pw_extrair_links(page, nome, uf)
            resultados.extend(r)
            log.info(f"{nome} ({url.split('/')[-1]}): {len(r)} relevantes")
        except Exception as e:
            log.warning(f"{nome}: {e}")
    return resultados


def scrape_sistema_s_playwright() -> list[dict]:
    """Scraping completo: Licitacoes-e + SEBRAE + SESC/SENAC + Petrobras via Playwright."""
    resultados = []
    sites_simples = [
        ("SESC-RJ", "https://www.sescrio.org.br/web/sesc/licitacoes", "RJ"),
        ("SENAC-RJ", "https://www.rj.senac.br/sobre-o-senac/licitacoes", "RJ"),
        ("SESC-SC", "https://www.sesc-sc.com.br/sescsc/licitacoes/", "SC"),
        ("SENAC-SC", "https://portal.sc.senac.br/", "SC"),
        ("SESI-SENAI", "https://licitacoes.portaldaindustria.com.br/", "BR"),
        ("FIRJAN", "https://portaldecompras.firjan.org.br/", "RJ"),
        ("CEDAE", "https://www.cedae.com.br/licitacao", "RJ"),
        ("NUCLEP", "https://www.nuclep.gov.br/licitacoes", "RJ"),
        ("COMLURB-eComprasRio", "https://ecomprasrio.rio.rj.gov.br/", "RJ"),
        ("CAIXA", "https://licitacoes.caixa.gov.br/", "RJ"),
        ("ELETRONUCLEAR", "https://www.eletronuclear.gov.br/Empresa/Licitacoes", "RJ"),
        ("TRANSPETRO", "https://transpetro.com.br/transpetro-institucional/licitacoes.htm", "RJ"),
        ("BNDES", "https://www.bndes.gov.br/wps/portal/site/home/transparencia/licitacoes-e-contratos", "RJ"),
        # AEGEA é multi-UF (CORSAN/RS, etc). Sem UF default — exige UF detectada do texto.
        ("AEGEA-Contratacoes", "https://fornecedores.aegea.com.br/contratacoes", ""),
        ("AEGEA-Engenharia", "https://fornecedores.aegea.com.br/contratacao/engenharia/", ""),
        ("AEGEA-Unidades", "https://fornecedores.aegea.com.br/contratacao/unidades/", ""),
        ("IGUA", "https://www.igua.com.br/fornecedores", "RJ"),
        ("ARIBA-Discovery", "https://service.ariba.com/Discovery.aw", "RJ"),
        ("MercadoEletronico", "https://www.me.com.br/supplier/login", "RJ"),
        ("NIMBI", "https://app.nimbi.com.br/", "RJ"),
    ]
    try:
        from playwright.sync_api import sync_playwright
        pw_instance = sync_playwright().start()

        def _new_browser_page():
            b = pw_instance.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"])
            p = b.new_page(user_agent=HEADERS["User-Agent"])
            p.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined})')
            return b, p

        browser, page = _new_browser_page()

        # 1. Licitacoes-e (BB) — com form interativo
        resultados.extend(scrape_licitacoes_e_pw(page))

        # 2. SEBRAE — tenta varios portais
        resultados.extend(scrape_sebrae_pw(page))

        # Reinicia browser pra proxima leva
        try:
            browser.close()
            browser, page = _new_browser_page()
        except Exception:
            pass

        # 3. Petronect (Petrobras) — login autenticado
        try:
            petronect_login = os.environ.get("PETRONECT_LOGIN", "")
            petronect_senha = os.environ.get("PETRONECT_SENHA", "")
            if petronect_login and petronect_senha:
                page.goto("https://www.petronect.com.br/", timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                # Tenta login
                user_input = page.query_selector("input[name*='user'], input[name*='login'], input[id*='user'], input[type='text']")
                pass_input = page.query_selector("input[type='password']")
                if user_input and pass_input:
                    user_input.fill(petronect_login)
                    pass_input.fill(petronect_senha)
                    btn = page.query_selector("button[type='submit'], input[type='submit']")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(8000)
                    r = _pw_extrair_links(page, "Petronect", "RJ")
                    resultados.extend(r)
                    log.info(f"Petronect (autenticado): {len(r)} residuos")
                else:
                    log.info("Petronect: campos de login nao encontrados")
        except Exception as e:
            log.warning(f"Petronect: {e}")

        # 3b. Petrobras Canal Fornecedor (publico)
        resultados.extend(scrape_petrobras_pw(page))

        # Reinicia browser
        try:
            browser.close()
            browser, page = _new_browser_page()
        except Exception:
            pass

        # 3c. SAP Ariba — login autenticado
        try:
            ariba_login = os.environ.get("ARIBA_LOGIN", "")
            ariba_senha = os.environ.get("ARIBA_SENHA", "")
            if ariba_login and ariba_senha:
                browser.close()
                browser, page = _new_browser_page()
                page.goto("https://service.ariba.com/Discovery.aw", timeout=40000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                # Tenta login
                user_input = page.query_selector("input[name*='user'], input[name*='User'], input[type='email'], input[id*='user']")
                pass_input = page.query_selector("input[type='password']")
                if user_input and pass_input:
                    user_input.fill(ariba_login)
                    pass_input.fill(ariba_senha)
                    btn = page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Log'), button:has-text('Sign')")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(10000)
                    r = _pw_extrair_links(page, "SAP Ariba", "RJ")
                    resultados.extend(r)
                    log.info(f"SAP Ariba (autenticado): {len(r)} residuos")
                else:
                    log.info("Ariba: campos de login nao encontrados, tentando SSO...")
                    # SAP pode usar SSO — tenta navegar direto
                    page.goto("https://service.ariba.com/Sourcing.aw", timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(5000)
                    r = _pw_extrair_links(page, "SAP Ariba", "RJ")
                    resultados.extend(r)
                    log.info(f"SAP Ariba (SSO): {len(r)} residuos")
        except Exception as e:
            log.warning(f"SAP Ariba: {e}")

        # Reinicia browser
        try:
            browser.close()
            browser, page = _new_browser_page()
        except Exception:
            pass

        # 3d. Mercado Eletronico — login autenticado
        try:
            me_login = os.environ.get("ME_LOGIN", "")
            me_senha = os.environ.get("ME_SENHA", "")
            if me_login and me_senha:
                browser.close()
                browser, page = _new_browser_page()
                page.goto("https://me.com.br/do/Login.mvc/LoginNew", timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                user_input = page.query_selector("#LoginName, input[name='LoginName']")
                pass_input = page.query_selector("#RAWSenha, input[name='RAWSenha']")
                if user_input and pass_input:
                    user_input.fill(me_login)
                    pass_input.fill(me_senha)
                    btn = page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Entrar'), button:has-text('Login')")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(8000)
                    # Navega pra oportunidades
                    page.goto("https://me.com.br/supplier/inbox/transactions/13", timeout=20000, wait_until="domcontentloaded")
                    page.wait_for_timeout(5000)
                    r = _pw_extrair_links(page, "Mercado Eletrônico", "RJ")
                    resultados.extend(r)
                    log.info(f"Mercado Eletrônico (autenticado): {len(r)} residuos")
                else:
                    log.info("ME: campos de login nao encontrados")
        except Exception as e:
            log.warning(f"Mercado Eletrônico: {e}")

        # 3e. Nimbi — login autenticado
        try:
            nimbi_login = os.environ.get("NIMBI_LOGIN", "")
            nimbi_senha = os.environ.get("NIMBI_SENHA", "")
            if nimbi_login and nimbi_senha:
                browser.close()
                browser, page = _new_browser_page()
                page.goto("https://app.nimbi.com.br/", timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                user_input = page.query_selector("input[type='email'], input[type='text'], input[name*='user'], input[name*='email'], input[name*='login']")
                pass_input = page.query_selector("input[type='password']")
                if user_input and pass_input:
                    user_input.fill(nimbi_login)
                    pass_input.fill(nimbi_senha)
                    btn = page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Entrar'), button:has-text('Login')")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(8000)
                    r = _pw_extrair_links(page, "Nimbi", "RJ")
                    resultados.extend(r)
                    log.info(f"Nimbi (autenticado): {len(r)} residuos")
                else:
                    log.info("Nimbi: campos de login nao encontrados")
        except Exception as e:
            log.warning(f"Nimbi: {e}")

        # Reinicia browser
        try:
            browser.close()
            browser, page = _new_browser_page()
        except Exception:
            pass

        # 4. CAIXA — clica "Participar" e extrai tabela
        try:
            page.goto("https://licitacoes.caixa.gov.br/", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            page.evaluate('() => { let b = document.getElementById("btFecharOutMensagem"); if(b) b.click(); }')
            page.wait_for_timeout(1000)
            page.evaluate('''() => {
                let links = document.querySelectorAll('a');
                for (let a of links) { if (a.name === 'j_idt50' || a.innerText.includes('Participar')) { a.click(); break; } }
            }''')
            page.wait_for_timeout(8000)
            rows = page.query_selector_all("table tr, .ui-datatable tr")
            for row in rows:
                txt = (row.inner_text() or "").strip()
                if len(txt) < 30:
                    continue
                if not any(k in txt.lower() for k in KEYWORDS_RESIDUOS):
                    continue
                link_tag = row.query_selector("a")
                href = ""
                if link_tag:
                    href = link_tag.get_attribute("href") or ""
                    if href and not href.startswith("http"):
                        href = f"https://licitacoes.caixa.gov.br{href}"
                resultados.append({
                    "fonte": "Caixa Econômica Federal",
                    "orgao": "CAIXA",
                    "objeto": txt[:250],
                    "uf": _detectar_uf_texto(txt) or "RJ",
                    "link": href,
                })
            log.info(f"CAIXA: {len([r for r in resultados if r.get('orgao') == 'CAIXA'])} residuos")
        except Exception as e:
            log.warning(f"CAIXA: {e}")

        # Reinicia browser pro lote final
        try:
            browser.close()
            browser, page = _new_browser_page()
        except Exception:
            pass

        # 5. Todos os sites simples — reinicia browser a cada 5
        for idx, (nome, url, uf) in enumerate(sites_simples):
            if idx > 0 and idx % 3 == 0:
                try:
                    browser.close()
                    browser, page = _new_browser_page()
                except Exception:
                    pass
            try:
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                r = _pw_extrair_links(page, nome, uf)
                resultados.extend(r)
                log.info(f"{nome}: {len(r)} relevantes")
            except Exception as e:
                log.warning(f"{nome}: {e}")

        browser.close()
        pw_instance.stop()
    except Exception as e:
        log.error(f"Playwright falhou completamente: {e}")
        try:
            pw_instance.stop()
        except Exception:
            pass
    return resultados


# ═══════════════════════════════════════════════════════════════
# FONTE 5: Petrobras (Canal Fornecedor + Petronect)
# ═══════════════════════════════════════════════════════════════
def scrape_petrobras() -> list[dict]:
    """Scraping Canal Fornecedor Petrobras — oportunidades publicas. Filtro rigido anti-institucional."""
    import re
    resultados = []
    # Apenas o endpoint oficial de oportunidades. /editais e /licitacoes nao existem (retornam 404/home).
    urls = [
        ("Petrobras-Oportunidades", "https://canalfornecedor.petrobras.com.br/oportunidades"),
    ]
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as cli:
        for nome, url in urls:
            try:
                r = cli.get(url)
                if r.status_code != 200:
                    log.info(f"{nome}: HTTP {r.status_code}")
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                # APENAS linhas de tabela estruturada (onde licitacao real aparece)
                for table in soup.find_all("table"):
                    rows = table.find_all("tr")
                    for row in rows[1:]:  # pula header
                        cells = row.find_all(["td", "th"])
                        texto = " ".join(c.get_text(" ", strip=True) for c in cells)
                        if len(texto) < 40:
                            continue
                        if not _match_interesse(texto):
                            continue
                        link_tag = row.find("a", href=True)
                        href = link_tag["href"] if link_tag else ""
                        if href and not href.startswith("http"):
                            href = f"https://canalfornecedor.petrobras.com.br{href}"
                        if _parece_institucional(texto, href):
                            continue
                        # Exige >= 2 sinais reais (num/data/valor/modalidade)
                        tl = texto.lower()
                        sinais = sum([
                            bool(re.search(r'\d{2,}/\d{4}|\d{4,}', texto)),
                            bool(re.search(r'\d{2}/\d{2}/\d{4}', texto)),
                            bool(re.search(r'r\$\s*[\d.,]+', tl)),
                            any(w in tl for w in ['edital', 'pregão', 'pregao', 'concorrência', 'concorrencia',
                                                  'dispensa de licitação', 'dispensa de licitacao',
                                                  'processo licitatório', 'processo licitatorio']),
                        ])
                        if sinais < 2:
                            continue
                        data_fim = ""
                        for c in cells:
                            t = c.get_text(strip=True)
                            if re.fullmatch(r'\d{2}/\d{2}/\d{4}', t):
                                data_fim = t
                        resultados.append({
                            "fonte": "Petrobras",
                            "orgao": "PETROBRAS",
                            "entidade": nome,
                            "objeto": texto[:250],
                            "uf": "RJ",
                            "encerramento": data_fim,
                            "link": href,
                        })
                log.info(f"{nome}: {len(resultados)} licitacoes reais (pos-filtro)")
            except Exception as e:
                log.warning(f"{nome}: {e}")
    return resultados


# ═══════════════════════════════════════════════════════════════
# EXECUCAO
# ═══════════════════════════════════════════════════════════════
def executar() -> dict:
    """Roda todos os scrapers e dispara novos no Telegram."""
    stats = {"fontes": 0, "encontrados": 0, "enviados": 0, "ja_enviados": 0, "erros": 0}
    sent = _load_sent()
    todos = []

    # Roda cada fonte
    fontes = [
        ("Portal Compras", scrape_portal_compras),
        ("Licitações-e", scrape_licitacoes_e),
        ("SEBRAE", scrape_sebrae),
        ("Petrobras", scrape_petrobras),
        ("Sistema S (Playwright)", scrape_sistema_s_playwright),
    ]
    for nome, fn in fontes:
        stats["fontes"] += 1
        try:
            items = fn()
            todos.extend(items)
            log.info(f"{nome}: {len(items)} resultados")
        except Exception as e:
            stats["erros"] += 1
            log.error(f"{nome}: {e}")

    stats["encontrados"] = len(todos)

    # Dedup e disparo
    for item in todos:
        uid = _hash_id(item.get("fonte", ""), item.get("objeto", ""), item.get("orgao", ""))
        if uid in sent:
            stats["ja_enviados"] += 1
            continue
        # Detecta nicho pra roteamento
        nicho = detectar_nicho(item.get("objeto", ""))
        uf_item = (item.get("uf") or "").upper()
        orgao_item = (item.get("orgao") or "").lower()
        msg = _formatar_sistema_s(item)

        # Filtro: Resíduos RJ OU Petrobras (qualquer UF)
        eh_petrobras = ("petrobras" in orgao_item or "transpetro" in orgao_item
                        or "petróleo brasileiro" in orgao_item
                        or "petroleo brasileiro" in orgao_item)

        if eh_petrobras:
            msg = "🛢 PETROBRAS\n\n" + msg
        elif nicho == "residuos" and uf_item == "RJ":
            msg = "♻️ RESÍDUOS RJ\n\n" + msg
        else:
            continue  # nada mais

        # VALIDAÇÃO: só envia se tiver link OU numero — evita mensagem incompleta
        if not item.get("link") and not item.get("numero"):
            log.warning(f"Ignorado (sem link/numero): {item.get('objeto', '')[:60]}")
            continue

        ok = enviar_para_nicho(msg, "residuos", parse_mode=None)

        if ok:
            sent.add(uid)
            stats["enviados"] += 1
            log.info(f"Enviado [{nicho}]: {item.get('objeto', '')[:60]}")
        else:
            stats["erros"] += 1

    _save_sent(sent)
    return stats


def executar_loop(intervalo_min: int = 120):
    log.info(f"bot_sistema_s iniciado. Intervalo: {intervalo_min}min")
    while True:
        try:
            log.info(f"Ciclo: {executar()}")
        except Exception as e:
            log.error(f"Erro: {e}")
        time.sleep(intervalo_min * 60)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=int, default=120, help="Minutos entre ciclos")
    ap.add_argument("--reset", action="store_true", help="Limpa historico")
    args = ap.parse_args()
    if args.reset:
        SENT_FILE.unlink(missing_ok=True)
        print("Reset OK.")
    if args.loop:
        executar_loop(args.intervalo)
    else:
        print(json.dumps(executar(), indent=2, ensure_ascii=False))
