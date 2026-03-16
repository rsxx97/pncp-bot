import json
import os
import sys
from datetime import date, datetime
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Importar banco de dados
sys.path.insert(0, SCRIPT_DIR)
from database import init_db, inserir_oportunidade, marcar_enviado

# Permite passar --config para usar outro arquivo de configuração
_config_arg = None
for i, arg in enumerate(sys.argv):
    if arg == "--config" and i + 1 < len(sys.argv):
        _config_arg = sys.argv[i + 1]
        break

CONFIG_PATH = _config_arg if _config_arg else os.path.join(SCRIPT_DIR, "config.json")
ENVIADOS_PATH = os.path.join(SCRIPT_DIR, "enviados.json")

PNCP_API_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

MODALIDADES_NOME = {
    1: "Leilão - Loss",
    2: "Diálogo Competitivo",
    3: "Concurso",
    4: "Concorrência - Loss",
    5: "Concorrência",
    6: "Pregão Eletrônico",
    7: "Pregão Presencial",
    8: "Dispensa de Licitação",
    9: "Inexigibilidade",
    10: "Manifestação de Interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão",
}


def carregar_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def carregar_enviados():
    if os.path.exists(ENVIADOS_PATH):
        with open(ENVIADOS_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def salvar_enviados(enviados):
    with open(ENVIADOS_PATH, "w", encoding="utf-8") as f:
        json.dump(list(enviados), f)


def consultar_pncp(config, modalidade, pagina=1, uf=None):
    import time
    from datetime import timedelta
    hoje = date.today()
    dias = config["paginacao"].get("dias_retroativos", 1)
    data_inicio = hoje - timedelta(days=dias)
    tam_pagina = max(config["paginacao"]["tamanho_pagina"], 10)
    uf_busca = uf if uf else config["filtros"]["uf"]
    params = {
        "dataInicial": data_inicio.strftime("%Y%m%d"),
        "dataFinal": hoje.strftime("%Y%m%d"),
        "codigoModalidadeContratacao": modalidade,
        "pagina": pagina,
        "tamanhoPagina": tam_pagina,
    }
    if uf_busca:
        params["uf"] = uf_busca
    for tentativa in range(3):
        try:
            resp = requests.get(PNCP_API_URL, params=params, timeout=60)
            resp.raise_for_status()
            text = resp.text.strip()
            if not text:
                return {"data": [], "totalPaginas": 0}
            return resp.json()
        except (requests.RequestException, ValueError):
            if tentativa < 2:
                time.sleep(5)
            else:
                raise


def gerar_id_contratacao(item):
    cnpj = item.get("orgaoEntidade", {}).get("cnpj", "")
    ano = item.get("anoCompra", "")
    seq = item.get("sequencialCompra", "")
    return f"{cnpj}-{ano}-{seq}"


def contem_palavra_chave(texto, palavras_chave):
    if not texto:
        return False
    texto_lower = texto.lower()
    return any(p.lower() in texto_lower for p in palavras_chave)


def formatar_valor(valor):
    if valor is None:
        return "Não informado"
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "Não informado"


def formatar_data(data_str):
    if not data_str:
        return "Não informada"
    try:
        dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return data_str


def montar_link(item):
    cnpj = item.get("orgaoEntidade", {}).get("cnpj", "")
    ano = item.get("anoCompra", "")
    seq = item.get("sequencialCompra", "")
    if cnpj and ano and seq:
        return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"
    link_origem = item.get("linkSistemaOrigem", "")
    if link_origem:
        return link_origem
    return "Não disponível"


def montar_mensagem(item):
    objeto = item.get("objetoCompra", "Sem descrição")
    if len(objeto) > 300:
        objeto = objeto[:300] + "..."

    orgao = item.get("orgaoEntidade", {}).get("razaoSocial", "Não informado")
    unidade = item.get("unidadeOrgao", {}).get("nomeUnidade", "Não informada")
    uf = item.get("unidadeOrgao", {}).get("ufSigla", "Não informada")
    valor = formatar_valor(item.get("valorTotalEstimado"))
    publicacao = formatar_data(item.get("dataPublicacaoPncp", item.get("dataAtualizacao")))
    abertura = formatar_data(item.get("dataAberturaProposta"))
    encerramento = formatar_data(item.get("dataEncerramentoProposta"))
    modalidade_cod = item.get("modalidadeId", item.get("codigoModalidadeContratacao", ""))
    modalidade_nome = MODALIDADES_NOME.get(modalidade_cod, f"Código {modalidade_cod}")
    link = montar_link(item)

    msg = (
        f"\U0001f4cc Modalidade: {modalidade_nome}\n"
        f"\U0001f3db Órgão: {orgao}\n"
        f"\U0001f3e2 Unidade Compradora: {unidade}\n"
        f"\U0001f4cd UF: {uf}\n"
        f"\U0001f5d3 Publicação PNCP: {publicacao}\n"
        f"\U0001f4e8 Início propostas: {abertura}\n"
        f"\u23f0 Fim propostas: {encerramento}\n"
        f"\U0001f6e0 Objeto: {objeto}\n"
        f"\U0001f4b0 Valor estimado: {valor}\n"
        f"\U0001f517 Link: {link}"
    )
    return msg


def enviar_telegram(config, mensagem):
    token = config["telegram"]["bot_token"]
    chat_id = config["telegram"]["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    if not resp.ok:
        print(f"[ERRO] Telegram: {resp.status_code} - {resp.text}")
    return resp.ok


def item_para_db(item):
    """Converte item da API PNCP para formato do banco de dados."""
    modalidade_cod = item.get("modalidadeId", item.get("codigoModalidadeContratacao", ""))
    return {
        "id": gerar_id_contratacao(item),
        "portal": "PNCP",
        "modalidade_cod": modalidade_cod,
        "modalidade_nome": MODALIDADES_NOME.get(modalidade_cod, f"Codigo {modalidade_cod}"),
        "orgao": item.get("orgaoEntidade", {}).get("razaoSocial", ""),
        "unidade": item.get("unidadeOrgao", {}).get("nomeUnidade", ""),
        "uf": item.get("unidadeOrgao", {}).get("ufSigla", ""),
        "objeto": item.get("objetoCompra", ""),
        "valor_estimado": item.get("valorTotalEstimado"),
        "data_publicacao": item.get("dataPublicacaoPncp", item.get("dataAtualizacao")),
        "data_abertura": item.get("dataAberturaProposta"),
        "data_encerramento": item.get("dataEncerramentoProposta"),
        "link": montar_link(item),
        "cnpj": item.get("orgaoEntidade", {}).get("cnpj", ""),
        "ano_compra": str(item.get("anoCompra", "")),
        "seq_compra": str(item.get("sequencialCompra", "")),
    }


def main():
    config = carregar_config()
    init_db()

    if config["telegram"]["bot_token"] == "SEU_TOKEN_AQUI":
        print("Configure o token do bot e o chat_id no config.json antes de executar.")
        sys.exit(1)

    enviados = carregar_enviados()
    novas = []

    # Suporte ao novo formato com grupos e ao formato antigo
    grupos = config["filtros"].get("grupos")
    if grupos is None:
        # Formato antigo: converte para grupo único
        grupos = [{
            "nome": "Geral",
            "modalidades": config["filtros"]["modalidades"],
            "palavras_chave": config["filtros"]["palavras_chave"],
        }]

    modalidades_consultadas = set()

    for grupo in grupos:
        nome_grupo = grupo.get("nome", "Sem nome")
        palavras_chave = grupo["palavras_chave"]
        modalidades = grupo["modalidades"]

        for modalidade in modalidades:
            # Evita consultar a mesma modalidade duas vezes na API
            if modalidade not in modalidades_consultadas:
                modalidades_consultadas.add(modalidade)

            pagina = 1
            while True:
                try:
                    dados = consultar_pncp(config, modalidade, pagina)
                except requests.RequestException as e:
                    print(f"[ERRO] Falha ao consultar PNCP ({nome_grupo}, modalidade {modalidade}, pág {pagina}): {e}")
                    break

                itens = dados.get("data", [])
                if not itens:
                    break

                for item in itens:
                    id_cont = gerar_id_contratacao(item)
                    if id_cont in enviados:
                        continue

                    objeto = item.get("objetoCompra", "")
                    palavras_exclusao = grupo.get("palavras_exclusao", config["filtros"].get("palavras_exclusao", []))
                    valor = item.get("valorTotalEstimado")
                    valor_minimo = config.get("valor_minimo", 0)
                    if valor is not None and float(valor) < valor_minimo:
                        continue
                    if contem_palavra_chave(objeto, palavras_chave) and not contem_palavra_chave(objeto, palavras_exclusao):
                        # Evita duplicata se já encontrado em outro grupo
                        if not any(idc == id_cont for idc, _ in novas):
                            novas.append((id_cont, item))

                total_paginas = dados.get("totalPaginas", 1)
                if pagina >= total_paginas:
                    break
                pagina += 1

    # Busca nacional: outros estados com valor acima de R$ 10 milhões
    valor_minimo_nacional = config.get("valor_minimo_nacional", 10000000)
    if valor_minimo_nacional > 0:
        uf_local = config["filtros"]["uf"]
        palavras_chave_todas = config["filtros"]["palavras_chave"]
        palavras_exclusao_todas = config["filtros"].get("palavras_exclusao", [])
        modalidades_nacionais = config["filtros"]["modalidades"]

        for modalidade in modalidades_nacionais:
            pagina = 1
            while True:
                try:
                    dados = consultar_pncp(config, modalidade, pagina, uf="")
                except requests.RequestException as e:
                    print(f"[ERRO] Falha busca nacional (modalidade {modalidade}, pág {pagina}): {e}")
                    break

                itens = dados.get("data", [])
                if not itens:
                    break

                for item in itens:
                    # Pula itens do estado local (já cobertos acima)
                    item_uf = item.get("unidadeOrgao", {}).get("ufSigla", "")
                    if item_uf == uf_local:
                        continue

                    id_cont = gerar_id_contratacao(item)
                    if id_cont in enviados:
                        continue

                    valor = item.get("valorTotalEstimado")
                    if valor is None or float(valor) < valor_minimo_nacional:
                        continue

                    objeto = item.get("objetoCompra", "")
                    if contem_palavra_chave(objeto, palavras_chave_todas) and not contem_palavra_chave(objeto, palavras_exclusao_todas):
                        if not any(idc == id_cont for idc, _ in novas):
                            novas.append((id_cont, item))

                total_paginas = dados.get("totalPaginas", 1)
                if pagina >= total_paginas:
                    break
                pagina += 1

    if not novas:
        print(f"[{datetime.now():%d/%m/%Y %H:%M}] Nenhuma nova oportunidade encontrada.")
        return

    print(f"[{datetime.now():%d/%m/%Y %H:%M}] {len(novas)} nova(s) oportunidade(s) encontrada(s).")

    for id_cont, item in novas:
        # Salvar no banco de dados
        db_item = item_para_db(item)
        inserir_oportunidade(db_item)

        # Enviar no Telegram
        msg = montar_mensagem(item)
        if enviar_telegram(config, msg):
            enviados.add(id_cont)
            marcar_enviado(id_cont)
            print(f"  Enviado: {id_cont}")
        else:
            print(f"  Falha ao enviar: {id_cont}")

    salvar_enviados(enviados)
    print("Concluido.")


if __name__ == "__main__":
    main()
