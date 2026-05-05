"""Bot Terceirização MDO — radar PNCP RJ.

Nicho: terceirização de mão de obra continuada (limpeza, copeiragem, ASG,
recepção, portaria, motorista, jardinagem, brigada não-armada, etc).
NÃO inclui vigilância armada (Miami), resíduos (SL), obra (Obra) nem TI (Aquisição TI).

Canal: TELEGRAM_BOT_TOKEN_MDO + TELEGRAM_CHAT_MDO no .env
Dedup: empresas/_compartilhado/data/terceirizacao_mdo_sent.json
"""
import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)

from shared.nichos import formatar_edital
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.skills._db_helper import gravar_edital

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_terceirizacao_mdo")

SENT_FILE = Path(__file__).parent.parent.parent / "empresas" / "_compartilhado" / "data" / "terceirizacao_mdo_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Reusa o NichoBot @k1RossiBot (mesmo do Construção) — só muda o canal
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_MDO") or os.getenv("TELEGRAM_BOT_TOKEN_OBRA") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_MDO") or os.getenv("TELEGRAM_CHAT_ID")

# Brasil inteiro — todas as 27 UFs com mesmo piso de valor mínimo
UFS_MDO = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG",
    "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR",
    "RS", "SC", "SE", "SP", "TO",
]
# Manutec tem atestado — sem limite máximo (filtro ME/EPP não se aplica)
VALOR_MAXIMO = float("inf")
# Piso uniforme para todo o BR — descarta editais com valor estimado < VALOR_MINIMO.
# Editais com valor sigiloso também são descartados (não há como aferir o piso).
VALOR_MINIMO = 10_000_000.0

# Keywords PNCP — terceirização de MDO continuada
KEYWORDS_BUSCA_PNCP = [
    "terceirização", "terceirizacao",
    "mão de obra", "mao de obra",
    "postos de trabalho", "posto de serviço", "posto de servico",
    "prestação de serviços continuados", "prestacao de servicos continuados",
    "asg", "auxiliar de serviços gerais", "auxiliar de servicos gerais",
    "agente de serviços gerais", "agente de servicos gerais",
    "limpeza e conservação", "limpeza e conservacao",
    "copeiragem", "copeiro",
    "recepcionista", "mensageria",
    "motorista",
    "jardinagem",
    "brigadista", "bombeiro civil",
    "porteiro", "portaria",
    "serviços gerais", "servicos gerais",
    "fornecimento de mão de obra", "fornecimento de mao de obra",
]

# MDO: só licitação tradicional. Dispensa removida (cliente já tem atestado, não precisa pegar contratação direta).
MODALIDADES_ACEITAS = (
    "Pregão Eletrônico", "Pregão Presencial",
    "Concorrência", "Concorrência - Loss",
    "Tomada de Preços", "Convite",
)
MODALIDADES_CONTRATACAO_DIRETA = ()  # vazio — não há aviso de contratação direta neste nicho

# Exclusões — nichos já cobertos por outros bots, falsos positivos
EXCLUSOES_MDO = [
    # Vigilância armada (vai pro canal Miami)
    "vigilância armada", "vigilancia armada",
    "segurança armada", "seguranca armada",
    "escolta armada", "transporte de valores",
    "vigilância patrimonial", "vigilancia patrimonial",
    "segurança patrimonial", "seguranca patrimonial",
    # Resíduos (vai pro canal SL)
    "resíduos", "residuos", "coleta de lixo",
    "limpeza pública", "limpeza publica",
    "coleta seletiva", "destinação final", "destinacao final",
    "varrição", "varricao",
    # Obras civis (vão pro canal Construção)
    "obra de construção", "obra de construcao",
    "reforma e ampliação", "reforma e ampliacao",
    "pavimentação", "pavimentacao",
    "engenharia civil",
    "construção civil", "construcao civil",
    # Padrões fortes de obra civil (objeto contém "mão de obra" como recurso, não como nicho)
    "obras de engenharia", "obra de engenharia",
    "execução de obra", "execucao de obra",
    "execução da obra", "execucao da obra",
    "obras e serviços de engenharia", "obras e servicos de engenharia",
    "obra civil", "obras civis",
    "fornecimento de materiais e mão de obra", "fornecimento de materiais e mao de obra",
    "fornecimento de material e mão de obra", "fornecimento de material e mao de obra",
    "empresa de engenharia", "empresa de engenharia/arquitetura",
    "engenharia/arquitetura",
    "execução de serviços de engenharia", "execucao de servicos de engenharia",
    "elaboração de projeto executivo", "elaboracao de projeto executivo",
    "recapeamento", "asfalt",
    "implantação de ciclo", "implantacao de ciclo",
    "extensão de rede", "extensao de rede",
    "iluminação pública", "iluminacao publica",
    "construção de unidade", "construcao de unidade",
    "construção de creche", "construcao de creche",
    "construção de escola", "construcao de escola",
    "construção de centro", "construcao de centro",
    "construção de barracão", "construcao de barracao",
    "construção de muro", "construcao de muro",
    "ampliação da sede", "ampliacao da sede",
    "ampliação do prédio", "ampliacao do predio",
    "ampliação da escola", "ampliacao da escola",
    "reforma da escola", "reforma da cozinha",
    "drenagem", "terraplanagem",
    "redemensionamento", "rede de baixa", "rede de média",
    "cobertura da arquibancada",
    "infraestrutura viária", "infraestrutura viaria",
    "passarela",
    # TI (vai pro canal Aquisição TI)
    "tecnologia da informação", "tecnologia da informacao",
    "manutenção de software", "manutencao de software",
    "manutenção de equipamento de informática", "manutencao de equipamento de informatica",
    "outsourcing de impressão", "outsourcing de impressao",
    # Veículos
    "manutenção de veículo", "manutencao de veiculo", "veicular",
    "manutenção de frota", "manutencao de frota",
    "caminhão pipa", "caminhao pipa",
    "locação de ônibus", "locacao de onibus",
    "locação de veículo", "locacao de veiculo",
    "transporte de passageiros", "transporte escolar",
    "ambulância", "ambulancia",
    # Compra/locação de equipamentos (não MDO)
    "equipamentos de jardinagem", "equipamentos de limpeza",
    "manutenção e operação de equipamento", "manutencao e operacao de equipamento",
    # Laboratório / análise (não MDO)
    "coleta, análise", "coleta, analise",
    "análise e emissão de laudo", "analise e emissao de laudo",
    "ensaios laboratoriais",
    # Outros não-MDO
    "remate de gado",
    "trabalho social", "serviços técnicos de trabalho",
    "execução de reforma", "execucao de reforma",
    "construção da arena", "construcao da arena",
    "implantação de piso", "implantacao de piso",
    # Aquisição pura (não é serviço)
    "aquisição de produto", "aquisicao de produto",
    "aquisição de material", "aquisicao de material",
    "aquisição de veículo", "aquisicao de veiculo",
    "aquisição de roçadeira", "aquisicao de rocadeira",
    "aquisição de máquina", "aquisicao de maquina",
    "aquisição de equipamento", "aquisicao de equipamento",
    "aquisição de tubulação", "aquisicao de tubulacao",
    "aquisição de trator", "aquisicao de trator",
    "aquisição de roçadeiras", "aquisicao de rocadeiras",
    "aquisição de mobiliário", "aquisicao de mobiliario",
    # Locação / fornecimento de equipamentos para evento (não MDO continuada)
    "locação de estrutura", "locacao de estrutura",
    "locação de sonorização", "locacao de sonorizacao",
    "locação de iluminação", "locacao de iluminacao",
    "locação de banheiro", "locacao de banheiro",
    "festa da cidade",
    # Transporte de passageiros (não MDO)
    "transporte terrestre, mediante",
    "fornecimento de veículos, motoristas",
    "fornecimento de veiculos, motoristas",
    # Construção
    "construção da primeira etapa", "construcao da primeira etapa",
    "construção do parque", "construcao do parque",
    "construção de parque", "construcao de parque",
    "execução completa da obra", "execucao completa da obra",
    "execução completa do cercamento", "execucao completa do cercamento",
    # Materiais para limpeza (não é MDO, é compra)
    "materiais para limpeza", "material para limpeza",
    "limpeza e conservação de veículos", "limpeza e conservacao de veiculos",
    # Limpeza pública / lixo (vai pro canal SL/resíduos)
    "limpeza urbana", "limpeza das vias", "limpeza de vias",
    "limpeza geral",
    # Películas / instalação eventual (não continuada)
    "instalação de película", "instalacao de pelicula",
    "instalação de divisória", "instalacao de divisoria",
]


def _eh_falso(objeto: str) -> bool:
    obj = (objeto or "").lower()
    return any(excl in obj for excl in EXCLUSOES_MDO)


# Match por combinação:
#   - Termo INEQUÍVOCO de MDO (terceirização, postos de trabalho, ASG, etc) sozinho — passa.
#   - "mão de obra" / "fornecimento de mão de obra" / "prestação de serviços continuados"
#     SÓ passam se acompanhados de uma função terceirizável (limpeza, copeiragem, ASG, etc).
KEYWORDS_INEQUIVOCAS = [
    r"\bterceiriza\w*",
    r"\bpostos?\s+de\s+(trabalho|servi[çc]os?)\b",
    r"\basg\b",
    r"\bauxiliar(es)?\s+de\s+servi[çc]os?\s+gerais\b",
    r"\bagente(s)?\s+de\s+servi[çc]os?\s+gerais\b",
    r"\blimpeza\s+e\s+conserva[çc][ãa]o\b",
    r"\bcopeiragem\b",
    r"\brecepcionista\b", r"\bmensageria\b",
    r"\bbrigadista\b", r"\bbombeiro\s+civil\b",
    r"\bporteiro\w*", r"\bportaria\b",
]

# Disparadores ambíguos: "mão de obra", "fornecimento de mão de obra",
# "prestação de serviços continuados", "contratação de empresa especializada"
GATILHOS_AMBIGUOS = [
    r"\bm[ãa]o\s+de\s+obra\b",
    r"\bfornecimento\s+de\s+m[ãa]o\s+de\s+obra\b",
    r"\bpresta[çc][ãa]o\s+de\s+servi[çc]os?\s+continu",
    r"\bcontrata[çc][ãa]o\s+de\s+empresa\s+especializada\b",
    r"\bservi[çc]os?\s+continuados?\b",
    r"\bservi[çc]os?\s+gerais\b",
    r"\bservi[çc]o\s+de\s+limpeza\b",
    r"\bservi[çc]os?\s+de\s+limpeza\b",
]

# Funções terceirizáveis — tem que aparecer JUNTO de um gatilho ambíguo
FUNCOES_TERCEIRIZAVEIS = [
    r"\blimpeza\b", r"\bconserva[çc][ãa]o\b", r"\bhigieniza[çc][ãa]o\b",
    r"\bcopeir\w*", r"\bcopa\b", r"\bgarçom\b", r"\bgarcom\b",
    r"\brecepcion\w+", r"\bmensageir\w+",
    r"\bmotorista\w*", r"\bjardin\w+", r"\bjardineiro\w*",
    r"\bbrigad\w+", r"\bbombeiro\s+civil\b", r"\bsocorrista\b",
    r"\bporteir\w*", r"\bportaria\b",
    r"\basg\b", r"\bauxiliar(es)?\s+de\s+servi[çc]os?\b",
    r"\bagente(s)?\s+de\s+servi[çc]os?\b",
    r"\bservente\w*", r"\bzelador\w*",
    r"\bvigilante\s+desarmado\b",
    r"\bcozinheir\w+", r"\bmerendeir\w+",
    r"\bcamareir\w+", r"\bdesinsetiza\w+",
    r"\bdedetiza\w+", r"\bdesratiza\w+",
    r"\bcontrol\w*\s+de\s+acesso\b",
    r"\bapoio\s+administrativo\b", r"\bapoio\s+operacional\b",
]


def _match_objeto_mdo(objeto: str) -> bool:
    """Aceita se:
       (a) houver keyword INEQUÍVOCA (terceirização, ASG, postos de trabalho, etc), ou
       (b) houver gatilho ambíguo (mão de obra / serviços continuados / etc)
           E também uma função terceirizável (limpeza, copeiragem, recepção, etc).
    """
    obj = (objeto or "").lower()
    if any(re.search(p, obj) for p in KEYWORDS_INEQUIVOCAS):
        return True
    tem_gatilho = any(re.search(p, obj) for p in GATILHOS_AMBIGUOS)
    if not tem_gatilho:
        return False
    return any(re.search(p, obj) for p in FUNCOES_TERCEIRIZAVEIS)


def _cabecalho(modalidade: str) -> str:
    h = "👥 TERCEIRIZAÇÃO DE MÃO DE OBRA\n\n"
    if any(m in (modalidade or "") for m in MODALIDADES_CONTRATACAO_DIRETA):
        h = "⚠️ CONTRATAÇÃO DIRETA — verifique se é cotação aberta\n\n" + h
    return h


def _load_sent() -> set:
    if SENT_FILE.exists():
        return set(json.loads(SENT_FILE.read_text(encoding="utf-8")))
    return set()


def _backup_sent():
    if not SENT_FILE.exists():
        return
    bdir = SENT_FILE.parent / "backups"
    bdir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy(SENT_FILE, bdir / f"terceirizacao_mdo_sent_{ts}.json")
    backups = sorted(bdir.glob("terceirizacao_mdo_sent_*.json"))
    for b in backups[:-10]:
        b.unlink(missing_ok=True)


def _save_sent(s: set):
    _backup_sent()
    SENT_FILE.write_text(json.dumps(sorted(s)), encoding="utf-8")


LOCK_FILE = SENT_FILE.parent / "terceirizacao_mdo.lock"
LOCK_TIMEOUT_MIN = 30


def _acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            age_min = (time.time() - LOCK_FILE.stat().st_mtime) / 60
            if age_min < LOCK_TIMEOUT_MIN:
                log.warning(f"⛔ Outra instância rodando ({age_min:.1f}min). Saindo.")
                return False
        except Exception:
            pass
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    LOCK_FILE.unlink(missing_ok=True)


def _post_telegram_com_retry(url: str, **kwargs) -> httpx.Response | None:
    for tentativa in range(3):
        try:
            r = httpx.post(url, **kwargs)
            if r.status_code == 429:
                try:
                    retry_after = r.json().get("parameters", {}).get("retry_after", 5)
                except Exception:
                    retry_after = 5
                log.warning(f"Telegram 429, aguardando {retry_after}s")
                time.sleep(retry_after + 1)
                continue
            return r
        except Exception as e:
            log.warning(f"Telegram POST: {e}")
            time.sleep(2)
    return None


def enviar_telegram(texto: str) -> bool:
    if not (BOT_TOKEN and CHAT_ID):
        log.error("TELEGRAM_BOT_TOKEN_MDO / CHAT não configurados")
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": texto, "disable_web_page_preview": True},
            timeout=20,
        )
        return r.status_code == 200
    except Exception as e:
        log.warning(f"Telegram: {e}")
        return False


def enviar_telegram_com_pdf(caption: str, pncp_id: str) -> bool:
    if not (BOT_TOKEN and CHAT_ID):
        return False
    try:
        cnpj, ano, seq = pncp_id.split("-")
    except ValueError:
        return enviar_telegram(caption)

    pdf_url = None
    titulo = "edital.pdf"
    try:
        r = httpx.get(
            f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
            timeout=15,
        )
        if r.status_code == 200:
            arquivos = r.json() or []
            edital = next((a for a in arquivos if a.get("tipoDocumentoNome") == "Edital"), None)
            escolhido = edital or (arquivos[0] if arquivos else None)
            if escolhido:
                pdf_url = escolhido.get("url") or escolhido.get("uri")
                titulo = escolhido.get("titulo") or titulo
    except Exception as e:
        log.warning(f"PNCP arquivos {pncp_id}: {e}")

    if not pdf_url:
        return enviar_telegram(caption)

    try:
        rr = httpx.get(pdf_url, timeout=60, follow_redirects=True)
        if rr.status_code != 200 or not rr.content:
            return enviar_telegram(caption)
        files = {"document": (titulo, rr.content, "application/pdf")}
        cap = caption if len(caption) <= 1024 else caption[:1020] + "…"
        data = {"chat_id": str(CHAT_ID), "caption": cap}
        s = _post_telegram_com_retry(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
            data=data, files=files, timeout=120,
        )
        return s is not None and s.status_code == 200
    except Exception as e:
        log.warning(f"sendDocument {pncp_id}: {e}")
        return enviar_telegram(caption)


def _enriquecer_edital(ed: dict) -> None:
    pid = ed.get("pncp_id", "")
    try:
        cnpj, ano, seq = pid.split("-")
    except ValueError:
        return
    detalhe = None
    for tentativa in range(3):
        try:
            r = httpx.get(
                f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}",
                timeout=30,
            )
            if r.status_code == 200:
                detalhe = r.json()
                break
            if r.status_code == 404:
                return
        except Exception:
            time.sleep(2)
    if detalhe is None:
        log.warning(f"Enriquecer {pid}: 3 tentativas falharam")
        return
    sigiloso_cod = detalhe.get("orcamentoSigilosoCodigo")
    ed["valor_sigiloso"] = sigiloso_cod is not None and sigiloso_cod != 1
    ed["valor_estimado"] = detalhe.get("valorTotalHomologado") or detalhe.get("valorTotalEstimado")
    if detalhe.get("dataAberturaProposta"):
        ed["data_abertura"] = detalhe["dataAberturaProposta"]
    if detalhe.get("dataEncerramentoProposta"):
        ed["data_encerramento"] = detalhe["dataEncerramentoProposta"]
    if detalhe.get("dataPublicacaoPncp"):
        ed["data_publicacao"] = detalhe["dataPublicacaoPncp"]
    if detalhe.get("objetoCompra"):
        ed["objeto"] = detalhe["objetoCompra"]
    if detalhe.get("modalidadeNome"):
        ed["modalidade"] = detalhe["modalidadeNome"]


def _buscar_editais_pncp_live() -> list[dict]:
    achados = {}
    for uf_alvo in UFS_MDO:
        for kw in KEYWORDS_BUSCA_PNCP:
            for pagina in range(1, 11):
                try:
                    r = httpx.get(
                        "https://pncp.gov.br/api/search/",
                        params={
                            "q": kw, "tipos_documento": "edital",
                            "status": "recebendo_proposta", "uf": uf_alvo,
                            "pagina": pagina, "tam_pagina": 50,
                        },
                        timeout=20,
                    )
                    if r.status_code != 200:
                        break
                    data = r.json()
                    items = data.get("items") or []
                    if not items:
                        break
                    for it in items:
                        uf_real = (it.get("uf") or "").upper()
                        if uf_real not in UFS_MDO:
                            continue
                        cnpj = it.get("orgao_cnpj") or ""
                        ano = it.get("ano") or ""
                        seq = it.get("numero_sequencial") or ""
                        if not (cnpj and ano and seq):
                            continue
                        pid = f"{cnpj}-{ano}-{seq}"
                        if pid in achados:
                            continue
                        achados[pid] = {
                            "pncp_id": pid,
                            "uf": uf_real,
                            "orgao_nome": it.get("orgao_nome") or "",
                            "unidade_nome": it.get("unidade_nome") or "",
                            "modalidade": it.get("modalidade_licitacao_nome") or "",
                            "objeto": it.get("description") or it.get("title") or "",
                            "data_publicacao": it.get("data_publicacao_pncp") or "",
                            "data_abertura": it.get("data_inicio_vigencia") or "",
                            "data_encerramento": it.get("data_fim_vigencia") or "",
                            "link_edital": "https://pncp.gov.br/app/editais/" + (
                                it.get("item_url", "").replace("/compras/", "")
                            ),
                            "fonte": "pncp",
                        }
                    total = data.get("total", 0)
                    if pagina * 50 >= total:
                        break
                    time.sleep(0.3)
                except Exception as e:
                    log.warning(f"PNCP search '{kw}' p{pagina}: {e}")
                    break
    return list(achados.values())


SAVE_INCREMENTAL_A_CADA = 10


def executar(dry_run: bool = False, bootstrap: bool = False) -> dict:
    stats = {"encontrados": 0, "enviados": 0, "ja_enviados": 0, "falhas": 0,
             "falsos_excluidos": 0, "modalidade_invalida": 0, "valor_acima": 0}
    if not bootstrap and not dry_run:
        if not _acquire_lock():
            stats["abortado_lock"] = True
            return stats

    try:
        sent = _load_sent()
        log.info("Consultando PNCP search (Terceirização MDO, RJ)...")
        editais = _buscar_editais_pncp_live()
        log.info(f"PNCP retornou {len(editais)} editais únicos abertos em RJ")

        candidatos = []
        for ed in editais:
            pncp_id = ed["pncp_id"]
            if pncp_id in sent:
                stats["ja_enviados"] += 1
                continue
            if _eh_falso(ed["objeto"] or ""):
                stats["falsos_excluidos"] += 1
                continue
            # Exige match literal de MDO no objeto (search PNCP é fuzzy, sem isso vaza obra/etc)
            if not _match_objeto_mdo(ed["objeto"] or ""):
                stats.setdefault("sem_match_local", 0)
                stats["sem_match_local"] += 1
                continue
            modal = ed["modalidade"] or ""
            modal_norm = re.sub(r"[\s\-_]+", " ", modal.lower()).strip()
            if not any(re.sub(r"[\s\-_]+", " ", m.lower()).strip() in modal_norm
                       for m in MODALIDADES_ACEITAS):
                stats["modalidade_invalida"] += 1
                continue
            # Filtro uniforme de valor: todo o BR precisa ter valor estimado >= VALOR_MINIMO
            _enriquecer_edital(ed)
            if ed.get("valor_sigiloso"):
                stats.setdefault("valor_sigiloso", 0)
                stats["valor_sigiloso"] += 1
                continue
            valor = ed.get("valor_estimado") or 0
            if valor < VALOR_MINIMO:
                stats.setdefault("abaixo_minimo", 0)
                stats["abaixo_minimo"] += 1
                continue
            candidatos.append(ed)

        stats["encontrados"] = len(candidatos)
        log.info(f"Candidatos pós-filtro inicial: {len(candidatos)}")

        if bootstrap:
            for ed in candidatos:
                sent.add(ed["pncp_id"])
                stats["enviados"] += 1
                if stats["enviados"] % SAVE_INCREMENTAL_A_CADA == 0:
                    _save_sent(sent)
            _save_sent(sent)
            log.info(f"Bot MDO: {json.dumps(stats, ensure_ascii=False)}")
            return stats

        if dry_run:
            for ed in candidatos:
                stats["enviados"] += 1
            log.info(f"Bot MDO: {json.dumps(stats, ensure_ascii=False)}")
            return stats

        for ed in candidatos:
            pncp_id = ed["pncp_id"]
            # Já foi enriquecido no pré-filtro de valor
            modal = ed.get("modalidade") or ""
            msg = _cabecalho(modal) + formatar_edital(ed)

            if enviar_telegram_com_pdf(msg, pncp_id):
                sent.add(pncp_id)
                stats["enviados"] += 1
                gravar_edital(ed, nicho="terceirizacao_mdo", enviado=True)
                log.info(f"Enviado {ed['uf']}: {pncp_id} ({stats['enviados']} no total)")
                if stats["enviados"] % SAVE_INCREMENTAL_A_CADA == 0:
                    _save_sent(sent)
                    log.info(f"💾 sent.json salvo ({stats['enviados']} editais)")
                time.sleep(5)
            else:
                stats["falhas"] += 1
                time.sleep(1)

        _save_sent(sent)
        log.info(f"Bot MDO: {json.dumps(stats, ensure_ascii=False)}")
        return stats
    finally:
        if not bootstrap and not dry_run:
            _release_lock()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bootstrap", action="store_true")
    args = ap.parse_args()
    executar(dry_run=args.dry_run, bootstrap=args.bootstrap)
