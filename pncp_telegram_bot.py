import json
import os
import sys
import time
import logging
from datetime import date, datetime, timedelta
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Importar banco de dados
sys.path.insert(0, SCRIPT_DIR)
from database import init_db, inserir_oportunidade, marcar_enviado, get_db

# Permite passar --config para usar outro arquivo de configuração
_config_arg = None
for i, arg in enumerate(sys.argv):
    if arg == "--config" and i + 1 < len(sys.argv):
        _config_arg = sys.argv[i + 1]
        break

CONFIG_PATH = _config_arg if _config_arg else os.path.join(SCRIPT_DIR, "config.json")
ENVIADOS_PATH = os.path.join(SCRIPT_DIR, "enviados.json")
LOCK_PATH = os.path.join(SCRIPT_DIR, "bot.lock")
LOG_PATH = os.path.join(SCRIPT_DIR, "bot.log")

PNCP_API_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

# Configura logging para arquivo e console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("pncp_bot")

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


# ── Lock file (impede execuções simultâneas) ──────────────────────────
def adquirir_lock():
    """Cria lock file. Retorna True se conseguiu, False se já tem outra instância."""
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH, "r") as f:
                info = json.load(f)
            pid = info.get("pid")
            inicio = info.get("inicio", "")
            # Se o lock tem mais de 30 minutos, é stale — remove
            if inicio:
                lock_time = datetime.fromisoformat(inicio)
                if (datetime.now() - lock_time).total_seconds() > 1800:
                    log.warning(f"Lock stale (PID {pid}, desde {inicio}). Removendo.")
                    os.remove(LOCK_PATH)
                else:
                    log.warning(f"Outra instância rodando (PID {pid}, desde {inicio}). Abortando.")
                    return False
        except (json.JSONDecodeError, ValueError, OSError):
            os.remove(LOCK_PATH)

    with open(LOCK_PATH, "w") as f:
        json.dump({"pid": os.getpid(), "inicio": datetime.now().isoformat()}, f)
    return True


def liberar_lock():
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


# ── Config e Enviados ─────────────────────────────────────────────────
def carregar_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def carregar_enviados():
    """Carrega IDs já enviados do arquivo JSON + banco de dados (dupla proteção)."""
    enviados = set()
    # Fonte 1: arquivo JSON
    if os.path.exists(ENVIADOS_PATH):
        try:
            with open(ENVIADOS_PATH, "r", encoding="utf-8") as f:
                enviados = set(json.load(f))
        except (json.JSONDecodeError, ValueError):
            log.warning("enviados.json corrompido, usando apenas banco de dados")
    # Fonte 2: banco de dados
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
    # Salva atomicamente (escreve em temp, depois renomeia)
    tmp_path = ENVIADOS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(sorted(enviados), f)
    os.replace(tmp_path, ENVIADOS_PATH)


# ── API PNCP ──────────────────────────────────────────────────────────
def consultar_pncp(config, modalidade, pagina=1, uf=None):
    hoje = date.today()
    dias = config["paginacao"].get("dias_retroativos", 1)
    data_inicio = hoje - timedelta(days=dias)
    tam_pagina = max(config["paginacao"]["tamanho_pagina"], 10)

    # uf=None → usa config; uf="" → sem filtro (nacional)
    if uf is None:
        uf_busca = config["filtros"]["uf"]
    else:
        uf_busca = uf

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
            resp = requests.get(PNCP_API_URL, params=params, timeout=90)
            resp.raise_for_status()
            text = resp.text.strip()
            if not text:
                return {"data": [], "totalPaginas": 0}
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            if tentativa < 2:
                log.warning(f"Tentativa {tentativa+1} falhou (mod={modalidade}, pag={pagina}): {e}")
                time.sleep(5 * (tentativa + 1))
            else:
                raise


# ── Funções auxiliares ────────────────────────────────────────────────
def gerar_id_contratacao(item):
    cnpj = item.get("orgaoEntidade", {}).get("cnpj", "")
    ano = item.get("anoCompra", "")
    seq = item.get("sequencialCompra", "")
    return f"{cnpj}-{ano}-{seq}"


def contem_palavra_chave(texto, palavras_chave):
    if not texto or not palavras_chave:
        return False
    texto_lower = texto.lower().replace("-", " ")
    return any(p.lower().replace("-", " ") in texto_lower for p in palavras_chave)


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


def montar_mensagem(item, id_cont=None):
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
        f"\U0001f3e2 Unidade: {unidade}\n"
        f"\U0001f4cd UF: {uf}\n"
        f"\U0001f5d3 Publicação: {publicacao}\n"
        f"\U0001f4e8 Início propostas: {abertura}\n"
        f"\u23f0 Fim propostas: {encerramento}\n"
        f"\U0001f6e0 Objeto: {objeto}\n"
        f"\U0001f4b0 Valor: {valor}\n"
        f"\U0001f517 {link}"
    )
    return msg


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
            log.error(f"Telegram: {resp.status_code} - {resp.text}")
        return resp.ok
    except requests.Timeout:
        log.warning("Telegram timeout - mensagem provavelmente entregue")
        return True
    except requests.RequestException as e:
        log.error(f"Telegram conexão: {e}")
        return False


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


# ── Coleta de licitações ──────────────────────────────────────────────
def coletar_local(config, enviados):
    """Busca licitações no estado (RJ) com filtro de palavras-chave."""
    novas = []
    palavras_chave = config["filtros"]["palavras_chave"]
    palavras_exclusao = config["filtros"].get("palavras_exclusao", [])
    modalidades = config["filtros"]["modalidades"]
    valor_minimo = config.get("valor_minimo", 0)

    for modalidade in modalidades:
        pagina = 1
        while True:
            try:
                dados = consultar_pncp(config, modalidade, pagina)
            except requests.RequestException as e:
                log.error(f"Falha PNCP local (mod={modalidade}, pag={pagina}): {e}")
                break

            itens = dados.get("data", [])
            if not itens:
                break

            for item in itens:
                id_cont = gerar_id_contratacao(item)
                if id_cont in enviados:
                    continue

                objeto = item.get("objetoCompra", "")
                valor = item.get("valorTotalEstimado")

                if valor is not None and float(valor) < valor_minimo:
                    continue

                if contem_palavra_chave(objeto, palavras_chave) and not contem_palavra_chave(objeto, palavras_exclusao):
                    if not any(idc == id_cont for idc, _ in novas):
                        novas.append((id_cont, item))

            total_paginas = dados.get("totalPaginas", 1)
            if pagina >= total_paginas:
                break
            pagina += 1

    return novas


def coletar_nacional(config, enviados, ja_coletados):
    """Busca licitações nacionais (limpeza acima de R$ 30M)."""
    novas = []
    valor_minimo_nacional = config.get("valor_minimo_nacional", 30000000)
    if valor_minimo_nacional <= 0:
        return novas

    uf_local = config["filtros"]["uf"]
    palavras_chave = config.get("palavras_chave_nacional", config["filtros"]["palavras_chave"])
    palavras_exclusao = config["filtros"].get("palavras_exclusao", [])
    # Nacional usa apenas pregão e concorrência
    modalidades = [5, 6]

    ids_ja = set(idc for idc, _ in ja_coletados)

    for modalidade in modalidades:
        pagina = 1
        while True:
            try:
                dados = consultar_pncp(config, modalidade, pagina, uf="")
            except requests.RequestException as e:
                log.error(f"Falha PNCP nacional (mod={modalidade}, pag={pagina}): {e}")
                break

            itens = dados.get("data", [])
            if not itens:
                break

            for item in itens:
                item_uf = item.get("unidadeOrgao", {}).get("ufSigla", "")
                if item_uf == uf_local:
                    continue

                id_cont = gerar_id_contratacao(item)
                if id_cont in enviados or id_cont in ids_ja:
                    continue

                valor = item.get("valorTotalEstimado")
                if valor is None or float(valor) < valor_minimo_nacional:
                    continue

                objeto = item.get("objetoCompra", "")
                if contem_palavra_chave(objeto, palavras_chave) and not contem_palavra_chave(objeto, palavras_exclusao):
                    if not any(idc == id_cont for idc, _ in novas):
                        novas.append((id_cont, item))

            total_paginas = dados.get("totalPaginas", 1)
            if pagina >= total_paginas:
                break
            pagina += 1

    return novas


# ── Envio com proteção anti-duplicata ─────────────────────────────────
def enviar_novas(config, novas, enviados):
    """Envia licitações novas no Telegram, uma a uma, com dedup robusto."""
    enviados_count = 0

    for id_cont, item in novas:
        # Re-verifica no banco ANTES de enviar (proteção contra concorrência)
        try:
            conn = get_db()
            row = conn.execute("SELECT enviado_telegram FROM oportunidades WHERE id=?", (id_cont,)).fetchone()
            conn.close()
            if row and row[0] == 1:
                log.info(f"  Já enviado (DB): {id_cont} — pulando")
                enviados.add(id_cont)
                continue
        except Exception:
            pass

        # Salvar no banco de dados
        db_item = item_para_db(item)
        inserir_oportunidade(db_item)

        # Enviar no Telegram
        msg = montar_mensagem(item, id_cont)
        sucesso = enviar_telegram(config, msg)

        if sucesso:
            # Marcar como enviado em TODAS as fontes
            enviados.add(id_cont)
            marcar_enviado(id_cont)
            salvar_enviados(enviados)
            log.info(f"  Enviado: {id_cont}")
            enviados_count += 1
        else:
            log.warning(f"  Falha ao enviar: {id_cont} (vai tentar na próxima execução)")

        # Delay entre mensagens para não throttle do Telegram
        time.sleep(1)

    return enviados_count


# ── Main ──────────────────────────────────────────────────────────────
def main():
    if not adquirir_lock():
        return

    try:
        config = carregar_config()
        init_db()

        if config["telegram"]["bot_token"] == "SEU_TOKEN_AQUI":
            log.error("Configure o token do bot e o chat_id no config.json antes de executar.")
            sys.exit(1)

        enviados = carregar_enviados()
        log.info(f"Iniciando busca. {len(enviados)} licitações já enviadas.")

        # 1. Busca local (RJ)
        novas_local = coletar_local(config, enviados)
        log.info(f"Local: {len(novas_local)} nova(s)")

        # 2. Busca nacional (limpeza > 30M)
        novas_nacional = coletar_nacional(config, enviados, novas_local)
        log.info(f"Nacional: {len(novas_nacional)} nova(s)")

        # Combina
        todas_novas = novas_local + novas_nacional

        if not todas_novas:
            log.info("Nenhuma nova oportunidade encontrada.")
            return

        log.info(f"Total: {len(todas_novas)} nova(s) oportunidade(s). Enviando...")

        # 3. Envia
        enviados_count = enviar_novas(config, todas_novas, enviados)
        log.info(f"Concluído. {enviados_count} enviada(s) no Telegram.")

    except Exception as e:
        log.exception(f"Erro fatal: {e}")
    finally:
        liberar_lock()


if __name__ == "__main__":
    main()
