"""
Scraper de licitações da EMOP-RJ (Empresa de Obras Públicas do Estado do RJ).
Raspa pregões eletrônicos e licitações presenciais do site da EMOP
e envia ao Telegram + salva no banco de dados.
"""
import json
import os
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from database import init_db, inserir_oportunidade, marcar_enviado, get_db

CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
ENVIADOS_PATH = os.path.join(SCRIPT_DIR, "enviados.json")

EMOP_URLS = {
    "pregao": "https://www.rj.gov.br/emop/preg%C3%A3o",
    "presencial": "https://www.rj.gov.br/emop/presencial",
}


def carregar_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def carregar_enviados():
    enviados = set()
    if os.path.exists(ENVIADOS_PATH):
        try:
            with open(ENVIADOS_PATH, "r", encoding="utf-8") as f:
                enviados = set(json.load(f))
        except (json.JSONDecodeError, ValueError):
            pass
    try:
        conn = get_db()
        rows = conn.execute("SELECT id FROM oportunidades WHERE enviado_telegram=1").fetchall()
        for r in rows:
            enviados.add(r[0])
        conn.close()
    except Exception:
        pass
    return enviados


def salvar_enviados(enviados):
    with open(ENVIADOS_PATH, "w", encoding="utf-8") as f:
        json.dump(list(enviados), f)


def raspar_emop(url, tipo="Pregão Eletrônico"):
    """Raspa licitações da página EMOP. Retorna lista de dicts."""
    resp = requests.get(url, timeout=60)
    resp.encoding = "utf-8"
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    body_field = soup.find("div", class_="field--name-body")
    if not body_field:
        print(f"[AVISO] Campo body não encontrado em {url}")
        return []

    licitacoes = []
    # Cada licitação está em blocos de <p> separados por <hr>
    # Padrão: <p><a href="...">Pregão nº XXX/YYYY</a></p><p>STATUS</p><p>OBJETO</p><hr>
    content_html = str(body_field)
    # Divide por <hr> ou <hr/>
    blocos = re.split(r"<hr\s*/?>", content_html)

    for bloco in blocos:
        bloco_soup = BeautifulSoup(bloco, "html.parser")

        # Buscar link com número do pregão/licitação
        link_tag = bloco_soup.find("a")
        if not link_tag:
            continue

        titulo = link_tag.get_text(strip=True)
        href = link_tag.get("href", "")

        # Extrair número (ex: "008/2026")
        num_match = re.search(r"(\d+/\d{4})", titulo)
        if not num_match:
            continue
        numero = num_match.group(1)
        ano = numero.split("/")[1]

        # Extrair todos os textos dos <p>
        paragraphs = bloco_soup.find_all("p")
        textos = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]

        # Status é geralmente o segundo texto (após o link)
        status = ""
        objeto = ""
        for i, t in enumerate(textos):
            if t == titulo:
                continue
            if not status and t in [
                "A Licitar", "Homologado", "Homologada", "Cancelado", "Cancelada",
                "Suspenso", "Suspensa", "Deserto", "Deserta", "Fracassado", "Fracassada",
                "Em Recurso", "Adiado Sine Die", "Revogado", "Revogada",
                "Em andamento", "Em Andamento",
            ]:
                status = t
            elif not objeto and len(t) > 20:
                objeto = t

        # Só interessa "A Licitar" (tempo hábil para cadastrar a Manutec)
        if status != "A Licitar":
            continue

        id_emop = f"EMOP-{tipo[:4]}-{numero.replace('/', '-')}"

        licitacoes.append({
            "id": id_emop,
            "numero": numero,
            "tipo": tipo,
            "status": status,
            "objeto": objeto,
            "link": href if href.startswith("http") else f"https://www.rj.gov.br{href}",
            "ano": ano,
        })

    return licitacoes


def contem_palavra_chave(texto, palavras_chave):
    if not texto:
        return False
    texto_lower = texto.lower().replace("-", " ")
    return any(p.lower().replace("-", " ") in texto_lower for p in palavras_chave)


def montar_mensagem_emop(lic):
    objeto = lic["objeto"]
    if len(objeto) > 300:
        objeto = objeto[:300] + "..."
    return (
        f"\U0001f3db [EMOP-RJ] {lic['tipo']}\n"
        f"\U0001f4cc Número: {lic['numero']}\n"
        f"\U0001f7e2 Status: {lic['status']}\n"
        f"\U0001f6e0 Objeto: {objeto}\n"
        f"\U0001f517 Link: {lic['link']}"
    )


def enviar_telegram(config, mensagem):
    token = config["telegram"]["bot_token"]
    chat_id = config["telegram"]["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if not resp.ok:
            print(f"[ERRO] Telegram: {resp.status_code} - {resp.text}")
        return resp.ok
    except requests.Timeout:
        print("[AVISO] Telegram timeout - mensagem provavelmente entregue")
        return True
    except requests.RequestException as e:
        print(f"[ERRO] Telegram conexão: {e}")
        return False


def main():
    config = carregar_config()
    init_db()

    if config["telegram"]["bot_token"] == "SEU_TOKEN_AQUI":
        print("Configure o token do bot no config.json antes de executar.")
        sys.exit(1)

    enviados = carregar_enviados()

    novas = []

    for nome, url in EMOP_URLS.items():
        tipo = "Pregão Eletrônico" if nome == "pregao" else "Licitação Presencial"
        print(f"Raspando EMOP {tipo}...")
        try:
            licitacoes = raspar_emop(url, tipo)
            print(f"  {len(licitacoes)} licitações ativas encontradas")
        except Exception as e:
            print(f"  [ERRO] Falha ao raspar {nome}: {e}")
            continue

        for lic in licitacoes:
            if lic["id"] in enviados:
                continue
            # EMOP é 100% obras/construção — envia tudo sem filtro
            novas.append(lic)

    if not novas:
        print(f"[{datetime.now():%d/%m/%Y %H:%M}] Nenhuma nova licitação EMOP encontrada.")
        return

    print(f"[{datetime.now():%d/%m/%Y %H:%M}] {len(novas)} nova(s) licitação(ões) EMOP.")

    for lic in novas:
        # Salvar no banco
        db_item = {
            "id": lic["id"],
            "portal": "EMOP",
            "modalidade_cod": 6 if "Pregão" in lic["tipo"] else 5,
            "modalidade_nome": lic["tipo"],
            "orgao": "EMOP - Empresa de Obras Públicas do Estado do RJ",
            "unidade": "EMOP-RJ",
            "uf": "RJ",
            "objeto": lic["objeto"],
            "valor_estimado": None,
            "data_publicacao": datetime.now().strftime("%Y-%m-%d"),
            "data_abertura": None,
            "data_encerramento": None,
            "link": lic["link"],
            "cnpj": "39039851000176",
            "ano_compra": lic["ano"],
            "seq_compra": lic["numero"].split("/")[0],
        }
        inserir_oportunidade(db_item)

        # Marca antes de enviar (evita duplicata)
        enviados.add(lic["id"])
        marcar_enviado(lic["id"])
        salvar_enviados(enviados)

        # Enviar Telegram
        msg = montar_mensagem_emop(lic)
        if enviar_telegram(config, msg):
            print(f"  Enviado: {lic['id']} - {lic['numero']}")
        else:
            enviados.discard(lic["id"])
            conn = get_db()
            conn.execute("UPDATE oportunidades SET enviado_telegram=0 WHERE id=?", (lic["id"],))
            conn.commit()
            conn.close()
            salvar_enviados(enviados)
            print(f"  Falha: {lic['id']}")

        time.sleep(1)

    print("Concluído.")


if __name__ == "__main__":
    main()
