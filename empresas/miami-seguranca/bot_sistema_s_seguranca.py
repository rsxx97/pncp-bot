"""Bot multi-portal — scraper de licitacoes de SEGURANCA/VIGILANCIA fora do PNCP.

Cliente: Miami Vigilancia e Seguranca LTDA — CNPJ 01.891.421/0001-12
Canal Telegram: MIAMI VIGILANCIA E SEGURANCA (@Miami_SV_Bot)
UF: somente RJ

11 portais focados em vigilancia/seguranca (fora do PNCP):
  1. Portal Compras Publicas
  2. Licitacoes-e (BB) — com captcha OCR, filtro RJ
  3. Petrobras (Canal Fornecedor)
  4. Petronect (login autenticado)
  5. Caixa Economica Federal (JSF)
  6. SESC-RJ
  7. SENAC-RJ
  8. FIRJAN
  9. COMLURB / eComprasRio (Prefeitura Rio)
  10. Portal Compras RJ (Governo do Estado)
  + PNCP via bot_vigilancia_rj.py

Zero API. Dedup em data/sistema_s_seguranca_sent.json.
Roda a cada 2h via Task Scheduler.
"""
import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# Importa modulos do licitacoes-ai
LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)

from shared.nichos import detectar_nicho, enviar_para_nicho, baixar_e_enviar_edital

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_sistema_s_seguranca")

SENT_FILE = Path(__file__).parent / "data" / "miami_seguranca_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Migra arquivo antigo para o novo (unificado)
_OLD_SENT = Path(__file__).parent / "data" / "sistema_s_seguranca_sent.json"
if _OLD_SENT.exists():
    _old = set(json.loads(_OLD_SENT.read_text(encoding="utf-8"))) if _OLD_SENT.stat().st_size > 2 else set()
    _new = set(json.loads(SENT_FILE.read_text(encoding="utf-8"))) if SENT_FILE.exists() else set()
    if _old:
        SENT_FILE.write_text(json.dumps(sorted(_old | _new)), encoding="utf-8")
    _OLD_SENT.unlink()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

UFS_INTERESSE = ["RJ"]

# Keywords de seguranca/vigilancia (Miami) — SEM termos genéricos
KEYWORDS_SEGURANCA = [
    # Vigilância patrimonial (NUNCA "vigilância" sozinha)
    "vigilância patrimonial", "vigilancia patrimonial",
    "vigilância armada", "vigilancia armada",
    "vigilância desarmada", "vigilancia desarmada",
    "vigilância orgânica", "vigilancia organica",
    "vigilância noturna", "vigilancia noturna",
    "vigilância eletrônica", "vigilancia eletronica",
    # Segurança patrimonial (NUNCA "segurança" sozinha)
    "segurança patrimonial", "seguranca patrimonial",
    "segurança armada", "seguranca armada",
    "segurança desarmada", "seguranca desarmada",
    "segurança eletrônica", "seguranca eletronica",
    "segurança privada", "seguranca privada",
    # Controle de acesso (NUNCA "portaria" sozinha)
    "controlador de acesso", "controle de acesso",
    "posto de portaria", "serviço de portaria", "servico de portaria",
    "porteiro", "guarita",
    # Bombeiro civil / brigadista (NUNCA "brigada" sozinha)
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
]

# Contextos que INVALIDAM match (falsos positivos)
EXCLUSOES_SEGURANCA = [
    r"vigil[aâ]ncia (sanit[aá]ria|ambiental|em sa[uú]de|epidemiol[oó]gica|alimentar)",
    r"seguran[cç]a (do trabalho|alimentar|p[uú]blica|vi[aá]ria|da informa[cç][aã]o|h[ií]drica|nuclear)",
    r"corpo de bombeiros",
    r"brigada de infantaria",
    r"brigada militar",
    r"recarga de extintor",
    r"manuten[cç][aã]o de extintor",
    r"an[aá]lises laboratoriais",
]


def _load_sent() -> set:
    if SENT_FILE.exists():
        return set(json.loads(SENT_FILE.read_text(encoding="utf-8")))
    return set()


def _save_sent(s: set):
    SENT_FILE.write_text(json.dumps(sorted(s)), encoding="utf-8")


def _hash_id(fonte: str, titulo: str, orgao: str) -> str:
    # Normaliza: lowercase, remove espacos extras, pontuacao variavel
    def _norm(s: str) -> str:
        s = re.sub(r'\s+', ' ', s.lower().strip())
        s = re.sub(r'[^\w\s]', '', s)  # remove pontuacao
        return s
    raw = f"{_norm(fonte)}|{_norm(titulo)[:120]}|{_norm(orgao)}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _match_interesse(texto: str) -> bool:
    t = texto.lower()
    return any(k in t for k in KEYWORDS_SEGURANCA)


def _formatar_sistema_s(item: dict) -> str:
    """Formata item no padrao IDENTICO ao PNCP. Só mostra campos com dado real."""
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
                        ('dispensa', 'Dispensa'), ('credenciamento', 'Credenciamento')]:
            if kw in objeto_raw.lower():
                modalidade = mod
                break
        if not modalidade:
            modalidade = "Licitação"

    if not valor_raw:
        m = re.search(r'R\$\s*([\d.,]+)', objeto_raw)
        if m:
            valor_raw = m.group(0)

    objeto = objeto_raw[:250] + "..." if len(objeto_raw) > 250 else objeto_raw

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


def _pw_extrair_links(page, nome: str, uf: str) -> list[dict]:
    """Extrai licitacoes reais (com numero/data/link) da pagina."""
    resultados = []
    for el in page.query_selector_all("tr, li, article, .card"):
        try:
            txt = (el.inner_text() or "").strip()
            if len(txt) < 20 or len(txt) > 600:
                continue
            txt_lower = txt.lower()
            if not any(k in txt_lower for k in KEYWORDS_SEGURANCA):
                continue
            # Filtro anti-falso positivo
            tem_numero = bool(re.search(r'\d{2,}/\d{4}|\d{4,}', txt))
            tem_data = bool(re.search(r'\d{2}/\d{2}/\d{4}', txt))
            tem_valor = 'r$' in txt_lower or 'valor' in txt_lower
            tem_licitacao = any(w in txt_lower for w in ['edital', 'pregão', 'pregao', 'processo', 'licitação', 'licitacao', 'dispensa', 'concorrência', 'concorrencia', 'contratação', 'contratacao'])
            if not (tem_numero or tem_data or tem_valor or tem_licitacao):
                continue
            # Filtro UF: licença operacional limita Miami ao RJ. Se texto menciona UF != RJ, descarta.
            tem_uf = re.search(r'\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SE|SP|TO)\b', txt)
            if tem_uf and tem_uf.group(1) != "RJ":
                continue
            href = ""
            link_tag = el.query_selector("a")
            if link_tag:
                href = link_tag.get_attribute("href") or ""
            data_match = re.search(r'(\d{2}/\d{2}/\d{4})', txt)
            encerramento = data_match.group(1) if data_match else ""
            num_match = re.search(r'(\d{2,}/\d{4})', txt)
            numero = num_match.group(1) if num_match else ""
            resultados.append({
                "fonte": nome,
                "orgao": nome,
                "objeto": txt[:250],
                "uf": uf,
                "link": href if href.startswith("http") else "",
                "encerramento": encerramento,
                "numero": numero,
            })
        except Exception:
            continue
    return resultados


# ═══════════════════════════════════════════════════════════════
# FONTE 1: Portal de Compras Publicas
# ═══════════════════════════════════════════════════════════════
def scrape_portal_compras(ufs: list[str] = None) -> list[dict]:
    if ufs is None:
        ufs = UFS_INTERESSE
    resultados = []
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as cli:
        for uf in ufs:
            try:
                url = f"https://www.portaldecompraspublicas.com.br/processos?uf={uf}&status=recebendo_propostas"
                r = cli.get(url)
                if r.status_code != 200:
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
                log.info(f"Portal Compras {uf}: {len([r for r in resultados if r['uf']==uf])} relevantes")
            except Exception as e:
                log.warning(f"Portal Compras {uf}: {e}")
    return resultados


# ═══════════════════════════════════════════════════════════════
# FONTE 2: Licitacoes-e (BB)
# ═══════════════════════════════════════════════════════════════
def scrape_licitacoes_e(ufs: list[str] = None) -> list[dict]:
    if ufs is None:
        ufs = UFS_INTERESSE
    resultados = []
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as cli:
        for uf in ufs:
            try:
                url = "https://licitacoes-e2.bb.com.br/aop/pesquisar-licitacao.aop"
                params = {"sgUf": uf, "situacao": "AB", "pagina": 1, "tamanhoPagina": 50}
                r = cli.get(url, params=params)
                if r.status_code == 200:
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
                                "link": it.get("link", "https://licitacoes-e.com.br"),
                            })
                    except Exception:
                        soup = BeautifulSoup(r.text, "html.parser")
                        for row in soup.select("tr, .licitacao, article, .card"):
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
            except Exception as e:
                log.warning(f"Licitações-e {uf}: {e}")
    return resultados




# ═══════════════════════════════════════════════════════════════
# FONTE 5: Playwright (21 portais)
# ═══════════════════════════════════════════════════════════════
def scrape_licitacoes_e_pw(page) -> list[dict]:
    """Licitacoes-e (BB) via Playwright — form + OCR captcha com keywords de seguranca."""
    resultados = []
    try:
        import ddddocr
        ocr = ddddocr.DdddOcr(show_ad=False)
    except Exception:
        log.warning("ddddocr nao disponivel, pulando Licitacoes-e")
        return []

    situacoes = [2, 3, 5, 6]
    termos = ["vigilancia", "seguranca", "portaria", "bombeiro", "brigada", "monitoramento"]

    for sit_idx in situacoes:
        for termo in termos:
            for tentativa in range(3):
                try:
                    page.goto("https://www.licitacoes-e.com.br/aop/pesquisar-licitacao.aop?opcao=preencherPesquisar",
                               timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)

                    page.evaluate(f'''() => {{
                        let sit = document.querySelector('select[name="select0"]');
                        if (sit) {{ sit.selectedIndex = {sit_idx}; sit.dispatchEvent(new Event('change')); }}
                        let uf = document.querySelector('select[name*="uf"], select[name*="Uf"], select[name*="UF"]');
                        if (uf) {{
                            for (let o of uf.options) {{ if (o.text.includes("RJ") || o.value === "RJ") {{ uf.value = o.value; uf.dispatchEvent(new Event('change')); break; }} }}
                        }}
                        let m = document.querySelector('input[name="textoMercadoria"]');
                        if (m) {{ m.value = "{termo}"; m.dispatchEvent(new Event("input")); }}
                    }}''')

                    captcha_img = None
                    for img in page.query_selector_all('img'):
                        box = img.bounding_box()
                        if box and box['width'] > 100 and box['height'] > 25 and box['y'] > 500:
                            captcha_img = img
                            break
                    if captcha_img:
                        captcha_text = ocr.classification(captcha_img.screenshot())
                        page.evaluate(f'''() => {{
                            let inputs = document.querySelectorAll('input[type="text"]');
                            let last; for(let i of inputs) {{ let r=i.getBoundingClientRect(); if(r.top>500 && r.width>50) last=i; }}
                            if(last) {{ last.value="{captcha_text}"; last.dispatchEvent(new Event("input")); }}
                        }}''')

                    page.evaluate('() => { document.querySelector("input[value=pesquisar]").form.submit(); }')
                    page.wait_for_timeout(6000)

                    body = page.inner_text("body")
                    if "incorreto" in body.lower() or "invalido" in body.lower():
                        continue
                    if "não encontrada" in body.lower():
                        break

                    for row in page.query_selector_all("tr"):
                        txt = (row.inner_text() or "").strip()
                        if len(txt) < 30:
                            continue
                        txt_lower = txt.lower()
                        if not any(k in txt_lower for k in KEYWORDS_SEGURANCA):
                            continue
                        # FILTRO RJ: so aceita se mencionar RJ no texto ou se nao tiver UF explicita
                        tem_uf = re.search(r'\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SE|SP|TO)\b', txt)
                        if tem_uf and tem_uf.group(1) != "RJ":
                            continue  # UF diferente de RJ, ignorar
                        link_tag = row.query_selector("a")
                        href = link_tag.get_attribute("href") if link_tag else ""
                        if href and not href.startswith("http"):
                            href = f"https://www.licitacoes-e.com.br{href}"
                        # Extrai link do edital pra download
                        edital_link = ""
                        for a in row.query_selector_all("a"):
                            h = a.get_attribute("href") or ""
                            t = (a.inner_text() or "").lower()
                            if "edital" in t or "anexo" in t or ".pdf" in h.lower():
                                if not h.startswith("http"):
                                    h = f"https://www.licitacoes-e.com.br{h}"
                                edital_link = h
                                break
                        resultados.append({
                            "fonte": "Licitações-e (BB)",
                            "orgao": "Sistema S / BB",
                            "objeto": txt[:250],
                            "uf": "RJ",
                            "link": href,
                            "edital_link": edital_link,
                        })
                    break
                except Exception as e:
                    log.warning(f"BB sit={sit_idx} termo={termo} t={tentativa}: {e}")
                    break

    log.info(f"Licitações-e: {len(resultados)} seguranca total")
    return resultados


def scrape_sistema_s_playwright() -> list[dict]:
    """Scraping completo: 21 portais via Playwright com keywords de seguranca."""
    resultados = []
    # Somente portais relevantes para VIGILANCIA/SEGURANCA no RJ
    # Removidos: CEDAE, NUCLEP, Eletronuclear, Transpetro, BNDES, SEBRAE,
    #            Aegea, Igua, Nimbi, SESI-SENAI, Ariba, ME (baixa chance de vigilancia)
    sites_simples = [
        # Sistema S — contratam vigilancia para unidades fisicas
        ("SESC-RJ", "https://www.sescrio.org.br/", "RJ"),
        ("SENAC-RJ", "https://www.rj.senac.br/sobre-o-senac/licitacoes", "RJ"),
        ("FIRJAN", "https://portaldecompras.firjan.com.br/", "RJ"),
        # Prefeitura do Rio — muita vigilancia
        ("COMLURB-eComprasRio", "https://ecomprasrio.rio.rj.gov.br/", "RJ"),
        # Portal estadual RJ
        ("ComprasRJ-Portal", "https://www.compras.rj.gov.br/", "RJ"),
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

        # 1. Licitacoes-e (BB) — form interativo
        resultados.extend(scrape_licitacoes_e_pw(page))

        # 2. Petrobras Canal Fornecedor + Petronect
        for nome, url, uf in [
            ("Petrobras", "https://canalfornecedor.petrobras.com.br/oportunidades", "RJ"),
        ]:
            try:
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
                r = _pw_extrair_links(page, nome, uf)
                resultados.extend(r)
                log.info(f"{nome}: {len(r)} relevantes")
            except Exception as e:
                log.warning(f"{nome}: {e}")

        # Reinicia browser
        try:
            browser.close()
            browser, page = _new_browser_page()
        except Exception:
            pass

        # 3. Petronect (login autenticado)
        try:
            petronect_login = os.environ.get("PETRONECT_LOGIN", "")
            petronect_senha = os.environ.get("PETRONECT_SENHA", "")
            if petronect_login and petronect_senha:
                page.goto("https://www.petronect.com.br/", timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
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
                    log.info(f"Petronect (autenticado): {len(r)} seguranca")
        except Exception as e:
            log.warning(f"Petronect: {e}")

        # Reinicia browser
        try:
            browser.close()
            browser, page = _new_browser_page()
        except Exception:
            pass

        # 5. Caixa — JSF (portal proprio, muita vigilancia)
        try:
            page.goto("https://licitacoes.caixa.gov.br/", timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            page.evaluate('() => { let b = document.getElementById("btFecharOutMensagem"); if(b) b.click(); }')
            page.wait_for_timeout(1000)
            page.evaluate('''() => {
                let links = document.querySelectorAll('a');
                for (let a of links) { if (a.name === 'j_idt50' || a.innerText.includes('Participar')) { a.click(); break; } }
            }''')
            page.wait_for_timeout(8000)
            for row in page.query_selector_all("table tr, .ui-datatable tr"):
                txt = (row.inner_text() or "").strip()
                if len(txt) < 30 or not any(k in txt.lower() for k in KEYWORDS_SEGURANCA):
                    continue
                # Filtro UF: licença operacional limita Miami ao RJ. CAIXA é nacional, então parseia UF do texto.
                tem_uf = re.search(r'\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SE|SP|TO)\b', txt)
                if tem_uf and tem_uf.group(1) != "RJ":
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
                    "uf": "RJ",
                    "link": href,
                })
            log.info(f"CAIXA: {len([r for r in resultados if r.get('orgao') == 'CAIXA'])} seguranca")
        except Exception as e:
            log.warning(f"CAIXA: {e}")

        # Reinicia browser
        try:
            browser.close()
            browser, page = _new_browser_page()
        except Exception:
            pass

        # 6. Sites simples — reinicia browser a cada 3
        for idx, (nome, url, uf) in enumerate(sites_simples):
            if idx > 0 and idx % 3 == 0:
                try:
                    browser.close()
                    browser, page = _new_browser_page()
                except Exception:
                    pass
            try:
                page.goto(url, timeout=35000, wait_until="domcontentloaded")
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
# EXECUCAO
# ═══════════════════════════════════════════════════════════════
def executar() -> dict:
    """Roda todos os scrapers e dispara novos no Telegram."""
    stats = {"fontes": 0, "encontrados": 0, "enviados": 0, "ja_enviados": 0, "erros": 0}
    sent = _load_sent()
    todos = []

    fontes = [
        ("Portal Compras Publicas", scrape_portal_compras),
        ("Licitações-e HTTP", scrape_licitacoes_e),
        ("Portais Playwright", scrape_sistema_s_playwright),
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

    for item in todos:
        uid = _hash_id(item.get("fonte", ""), item.get("objeto", ""), item.get("orgao", ""))
        if uid in sent:
            stats["ja_enviados"] += 1
            continue
        nicho = detectar_nicho(item.get("objeto", ""))
        msg = _formatar_sistema_s(item)

        # SOMENTE seguranca RJ — ignora todo o resto
        uf_item = (item.get("uf") or "").upper()
        if nicho != "seguranca" or uf_item not in ("RJ", ""):
            continue

        # Validacao: so envia se tiver link OU numero
        if not item.get("link") and not item.get("numero"):
            log.warning(f"Ignorado (sem link/numero): {item.get('objeto', '')[:60]}")
            continue

        ok = enviar_para_nicho(msg, "seguranca", parse_mode=None)

        if ok:
            sent.add(uid)
            stats["enviados"] += 1
            log.info(f"Enviado [seguranca]: {item.get('objeto', '')[:60]}")
            # Envia edital PDF junto se tiver link
            edital_url = item.get("edital_link") or item.get("link") or ""
            if edital_url and edital_url.startswith("http"):
                try:
                    nome_edital = item.get("numero") or uid
                    caption = f"📄 Edital — {item.get('orgao', '')[:40]}"
                    baixar_e_enviar_edital(edital_url, nome_edital, caption, "seguranca")
                    log.info(f"Edital enviado: {edital_url[:60]}")
                except Exception as e:
                    log.warning(f"Edital nao enviado: {e}")
        else:
            stats["erros"] += 1

    _save_sent(sent)
    return stats


def executar_loop(intervalo_min: int = 120):
    log.info(f"bot_sistema_s_seguranca iniciado. Intervalo: {intervalo_min}min")
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
