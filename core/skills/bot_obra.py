"""Bot Obra unificado — radar de construção e manutenção predial.

Combina B7 (obra geral SC+RJ) + Manutec (manutenção predial RJ) em um único disparo.
Cada edital é classificado em UM perfil (não duplica) e enviado uma vez no canal OBRA.

Dedup: data/obra_sent.json
Canal: TELEGRAM_BOT_TOKEN_OBRA + TELEGRAM_CHAT_OBRA no .env
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

from shared.nichos import formatar_edital, detectar_nicho

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot_obra")

SENT_FILE = Path(__file__).parent.parent.parent / "empresas" / "_compartilhado" / "data" / "obra_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_OBRA") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_OBRA") or os.getenv("TELEGRAM_CHAT_ID")

UFS_OBRA = ["SC", "RJ"]

KEYWORDS_MANUTENCAO = [
    "manutenção predial", "manutencao predial",
    "manutenção preventiva", "manutencao preventiva",
    "manutenção corretiva", "manutencao corretiva",
    "manutenção elétrica", "manutencao eletrica",
    "manutenção hidráulica", "manutencao hidraulica",
    "ar condicionado", "climatização", "climatizacao",
    "hvac", "elevador", "instalações prediais", "instalacoes prediais",
    "serviços de engenharia", "servicos de engenharia",
]

# Exclusões — objetos que mencionam "obra"/"manutenção" mas NÃO são obra/reforma/manutenção predial.
EXCLUSOES_OBRA = [
    # Veículos / frota
    "veículo", "veicular", "veiculo",
    "caminhão", "caminhao", "ônibus", "onibus", "viatura", "frota",
    "automotor", "automotiv",
    "manutenção de máquina", "manutencao de maquina", "máquina pesada", "maquina pesada",
    "trator", "retroescavadeira", "escavadeira", "pá-carregadeira", "pa-carregadeira",
    "motoniveladora", "rolo compactador",
    "revisão de garantia", "revisao de garantia",
    # TI / software / sistemas
    "manutenção de software", "manutencao de software",
    "manutenção de impressora", "manutencao de impressora",
    "manutenção informática", "manutencao informatica",
    "manutenção de microcomputador", "manutencao de microcomputador",
    "manutenção de notebook", "manutencao de notebook",
    "manutenção de servidor", "manutencao de servidor",
    "telefonia", "manutenção de telefon",
    "manutenção corretiva e evolutiva", "manutencao corretiva e evolutiva",
    "manutenção evolutiva", "manutencao evolutiva",
    "aplicações de backoffice", "aplicacoes de backoffice", "backoffice",
    "ambiente tecnológico", "ambiente tecnologico",
    "sistema corporativo", "sistemas corporativos",
    "erp", "crm", "datacenter", "data center",
    "licença de software", "licenca de software",
    "desenvolvimento de software", "desenvolvimento de sistema",
    "manutenção de aplicação", "manutencao de aplicacao",
    "manutenção de aplicações", "manutencao de aplicacoes",
    "tecnologia da informação", "tecnologia da informacao", "ti corporativ",
    "outsourcing de impressão", "outsourcing de impressao",
    "active directory", "office 365", "microsoft 365",
    # Telecom / Internet
    "serviço de internet", "servico de internet",
    "link dedicado", "link de dados",
    "gpon", "wi-fi", "wifi",
    "provedor de internet", "provedor de acesso",
    "telecomunicações", "telecomunicacoes",
    "internet por meio", "acesso à internet", "acesso a internet",
    "fibra óptica", "fibra optica",  # quando é serviço, não infraestrutura
    # Aquisição pura de material (sem execução de obra)
    "aquisição de material de construção", "aquisicao de material de construcao",
    "aquisição de materiais de construção", "aquisicao de materiais de construcao",
    "aquisição de cimento", "aquisicao de cimento",
    # Outros não-prediais
    "manutenção de equipamento médico", "manutencao de equipamento medico",
    "manutenção odontológic", "manutencao odontologic",
    "manutenção de balança", "manutencao de balanca",
]


def _eh_falso_obra(objeto: str) -> bool:
    """True se objeto é falso-positivo de obra (veículo, TI, aquisição pura, etc)."""
    obj = (objeto or "").lower()
    return any(excl in obj for excl in EXCLUSOES_OBRA)


# Palavras de obra com bordas de palavra (\b...\b). Cada match conta 1 ponto no score.
# Exigir score >= 2 evita falsos onde a palavra aparece de passagem.
KEYWORDS_OBRA_REGEX = [
    r"\bobras?\b", r"\breforma\w*", r"\bconstru[çc][ãa]o\b", r"\bconstruir\b",
    r"\bamplia[çc][ãa]o\b", r"\bedifica[çc][ãa]o\b", r"\bedif[íi]cios?\b",
    r"\bpavimenta[çc][ãa]o\b", r"\bdrenagem\b",
    r"\burbaniza[çc][ãa]o\b", r"\bimpermeabiliza[çc][ãa]o\b",
    r"\bengenharia\s+civil\b", r"\binfraestrutura\b",
    r"\baterro\b", r"\bmuro\b", r"\btalude\b", r"\bcortina\s+atirantada\b",
    r"\brevitaliza[çc][ãa]o\b", r"\brecupera[çc][ãa]o\s+de\s+(obra|pista|via|vias)",
    r"\bpredial\b", r"\bpr[eé]dios?\b",
    r"\bunidades?\s+habitacion", r"\bhabitacional\b",
    r"\bservi[çc]os?\s+de\s+engenharia\b",
    r"\bempreitada\b", r"\bcanteiro\s+de\s+obra",
    r"\brodovia\b", r"\bpontes?\b",
    r"\bsinaliza[çc][ãa]o\s+(viária|viaria|de\s+tr[âa]nsito)",
]


def _score_obra(objeto: str) -> int:
    """Conta quantas keywords distintas de obra aparecem (word-boundary). Maior = mais provável obra real."""
    obj_l = (objeto or "").lower()
    return sum(1 for pat in KEYWORDS_OBRA_REGEX if re.search(pat, obj_l))


def _aceita_obra(objeto: str) -> bool:
    """Decide se aceita o edital. Aceita se: manutenção predial OU score obra >= 2.
    Rejeita se exclusão explícita (vehiculo/TI/internet/etc)."""
    if _eh_falso_obra(objeto):
        return False
    if _eh_manutencao(objeto):
        return True
    return _score_obra(objeto) >= 2

MODALIDADES_ACEITAS = (
    "Pregão Eletrônico", "Pregão Presencial",
    "Concorrência", "Concorrência - Loss",
    "Tomada de Preços", "Convite",
    "Dispensa", "Dispensa de Licitação",
)
MODALIDADES_CONTRATACAO_DIRETA = (
    "Dispensa", "Dispensa de Licitação",
    "Inexigibilidade", "Inexigibilidade de Licitação",
)


def _eh_manutencao(objeto: str) -> bool:
    obj = (objeto or "").lower()
    return any(kw in obj for kw in KEYWORDS_MANUTENCAO)


def _cabecalho(modalidade: str) -> str:
    h = "🏗 OBRA / REFORMA / MANUTENÇÃO PREDIAL\n\n"
    if any(m in (modalidade or "") for m in MODALIDADES_CONTRATACAO_DIRETA):
        h = "⚠️ CONTRATAÇÃO DIRETA — verifique se é cotação aberta\n\n" + h
    return h


def _load_sent() -> set:
    if SENT_FILE.exists():
        return set(json.loads(SENT_FILE.read_text(encoding="utf-8")))
    return set()


def _backup_sent():
    """Cópia do sent.json antes de modificar. Mantém últimos 10 backups."""
    if not SENT_FILE.exists():
        return
    bdir = SENT_FILE.parent / "backups"
    bdir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy(SENT_FILE, bdir / f"obra_sent_{ts}.json")
    backups = sorted(bdir.glob("obra_sent_*.json"))
    for b in backups[:-10]:
        b.unlink(missing_ok=True)


def _save_sent(s: set):
    _backup_sent()
    SENT_FILE.write_text(json.dumps(sorted(s)), encoding="utf-8")


LOCK_FILE = SENT_FILE.parent / "obra.lock"
LOCK_TIMEOUT_MIN = 30  # lock stale após 30min é considerado abandono


def _acquire_lock() -> bool:
    """True se conseguiu o lock. False se outra instância está rodando."""
    if LOCK_FILE.exists():
        try:
            age_min = (time.time() - LOCK_FILE.stat().st_mtime) / 60
            if age_min < LOCK_TIMEOUT_MIN:
                log.warning(f"⛔ Outra instância rodando (lock há {age_min:.1f}min). Saindo.")
                return False
            log.warning(f"⚠️ Lock stale ({age_min:.1f}min) — removendo")
        except Exception:
            pass
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    LOCK_FILE.unlink(missing_ok=True)


BOT_USERNAME_OBRA = os.getenv("BOT_USERNAME_OBRA", "k1RossiBot")


def _url_pdf_direto(pncp_id: str) -> str | None:
    """Consulta API PNCP de arquivos e retorna URL do edital principal pra download direto.
    None se a API falhar ou não houver arquivos."""
    try:
        cnpj, ano, seq = pncp_id.split("-")
    except ValueError:
        return None
    try:
        r = httpx.get(
            f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
            timeout=10,
        )
        if r.status_code != 200:
            return None
        arquivos = r.json() or []
        # Prioriza tipoDocumentoNome == "Edital"; senão pega o primeiro
        edital = next((a for a in arquivos if a.get("tipoDocumentoNome") == "Edital"), None)
        escolhido = edital or (arquivos[0] if arquivos else None)
        if escolhido:
            return escolhido.get("url") or escolhido.get("uri")
    except Exception:
        pass
    return None


def _build_inline_keyboard(edital: dict) -> dict | None:
    """Botão de download direto do PDF do edital (1 clique). Fallback: deep link DM."""
    pncp_id = (edital.get("pncp_id") or "").strip()
    if not pncp_id:
        return None
    pdf_url = _url_pdf_direto(pncp_id)
    if pdf_url:
        return {"inline_keyboard": [[{"text": "📄 Abrir Edital", "url": pdf_url}]]}
    # Fallback: deep link → listener envia o PDF na DM
    deep = f"https://t.me/{BOT_USERNAME_OBRA}?start=ed_{pncp_id}"
    return {"inline_keyboard": [[{"text": "📄 Baixar Edital (DM)", "url": deep}]]}


def enviar_telegram(texto: str, reply_markup: dict | None = None) -> bool:
    if not (BOT_TOKEN and CHAT_ID):
        log.error("TELEGRAM_BOT_TOKEN_OBRA / TELEGRAM_CHAT_OBRA não configurados")
        return False
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=20)
        return r.status_code == 200
    except Exception as e:
        log.warning(f"Telegram: {e}")
        return False


def _post_telegram_com_retry(url: str, **kwargs) -> httpx.Response | None:
    """POST no Telegram com retry em 429 (Too Many Requests) respeitando Retry-After."""
    for tentativa in range(3):
        try:
            r = httpx.post(url, **kwargs)
            if r.status_code == 429:
                try:
                    retry_after = r.json().get("parameters", {}).get("retry_after", 5)
                except Exception:
                    retry_after = 5
                log.warning(f"Telegram 429, aguardando {retry_after}s (tentativa {tentativa+1}/3)")
                time.sleep(retry_after + 1)
                continue
            return r
        except Exception as e:
            log.warning(f"Telegram POST: {e}")
            time.sleep(2)
    return None


def enviar_telegram_com_pdf(caption: str, pncp_id: str) -> bool:
    """Anexa o PDF do edital direto na mensagem. Fallback p/ texto-só se não houver PDF."""
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
        # Caption do Telegram tem limite de 1024 chars
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


KEYWORDS_BUSCA_PNCP = [
    "obra", "reforma", "construção",
    "manutenção predial", "manutenção preventiva", "manutenção corretiva",
    "ampliação", "edificação", "pavimentação",
    "engenharia civil", "infraestrutura", "elevador",
    "ar condicionado", "climatização", "drenagem",
]


def _enriquecer_edital(ed: dict) -> None:
    """GET no PNCP detalhado com retries — PNCP é intermitente.
    Timeout 30s, até 3 tentativas. Preenche valor/datas/sigiloso."""
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
    """Consulta PNCP search por todas as keywords, dedupe, filtra UF (search PNCP é falho).
    Retorna lista de dicts compatível com formatar_edital()."""
    achados = {}
    for uf_alvo in UFS_OBRA:
        for kw in KEYWORDS_BUSCA_PNCP:
            for pagina in range(1, 11):  # até 10 páginas (500 items) por keyword
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
                        if uf_real not in UFS_OBRA:
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
                            "valor": it.get("valor_global"),
                            "link_edital": "https://pncp.gov.br/app/editais/" + (
                                it.get("item_url", "").replace("/compras/", "")
                            ),
                            "fonte": "pncp",  # "pncp" suprime a linha "📡 Fonte:" no formatador
                        }
                    total = data.get("total", 0)
                    if pagina * 50 >= total:
                        break
                    time.sleep(0.3)
                except Exception as e:
                    log.warning(f"PNCP search '{kw}'/{uf_alvo} p{pagina}: {e}")
                    break
    return list(achados.values())


SAVE_INCREMENTAL_A_CADA = 10  # salva sent.json a cada N envios


def executar(dry_run: bool = False, bootstrap: bool = False) -> dict:
    """Roda 1 ciclo. Busca PNCP live, aplica filtros, envia novos. Bootstrap marca sem disparar."""
    stats = {"encontrados": 0, "enviados": 0, "ja_enviados": 0, "falhas": 0,
             "falsos_excluidos": 0, "score_baixo": 0, "modalidade_invalida": 0}
    if not bootstrap and not dry_run:
        if not _acquire_lock():
            stats["abortado_lock"] = True
            return stats

    try:
        sent = _load_sent()

        log.info("Consultando PNCP search (15 keywords × 2 UFs, com paginação)...")
        editais = _buscar_editais_pncp_live()
        log.info(f"PNCP retornou {len(editais)} editais únicos abertos em SC+RJ")

        # Pré-filtros (rápidos) antes do enrichment paralelo
        candidatos = []
        for ed in editais:
            pncp_id = ed["pncp_id"]
            if pncp_id in sent:
                stats["ja_enviados"] += 1
                continue
            objeto = ed["objeto"] or ""
            if _eh_falso_obra(objeto):
                stats["falsos_excluidos"] += 1
                continue
            if not (_eh_manutencao(objeto) or _score_obra(objeto) >= 2):
                stats["score_baixo"] += 1
                continue
            modal = ed["modalidade"] or ""
            if not any(m.lower() in modal.lower() for m in MODALIDADES_ACEITAS):
                stats["modalidade_invalida"] += 1
                continue
            candidatos.append(ed)

        stats["encontrados"] = len(candidatos)
        log.info(f"Candidatos pós-filtro: {len(candidatos)}")

        if bootstrap:
            for ed in candidatos:
                sent.add(ed["pncp_id"])
                stats["enviados"] += 1
                if stats["enviados"] % SAVE_INCREMENTAL_A_CADA == 0:
                    _save_sent(sent)
            _save_sent(sent)
            log.info(f"Bot Obra: {json.dumps(stats, ensure_ascii=False)}")
            return stats

        if dry_run:
            for ed in candidatos:
                stats["enviados"] += 1
            log.info(f"Bot Obra: {json.dumps(stats, ensure_ascii=False)}")
            return stats

        for ed in candidatos:
            pncp_id = ed["pncp_id"]
            _enriquecer_edital(ed)  # busca valor/datas; falha silenciosa
            modal = ed.get("modalidade") or ""
            msg = _cabecalho(modal) + formatar_edital(ed)

            if enviar_telegram_com_pdf(msg, pncp_id):
                sent.add(pncp_id)
                stats["enviados"] += 1
                log.info(f"Enviado {ed['uf']}: {pncp_id} ({stats['enviados']} no total)")
                # SAVE INCREMENTAL: a cada 10 envios persiste sent.json
                # garante que se o processo for morto, não perde os já enviados
                if stats["enviados"] % SAVE_INCREMENTAL_A_CADA == 0:
                    _save_sent(sent)
                    log.info(f"💾 sent.json salvo ({stats['enviados']} editais)")
                time.sleep(5)  # throttle
            else:
                stats["falhas"] += 1
                time.sleep(1)

        if not dry_run:
            _save_sent(sent)  # save final
        log.info(f"Bot Obra: {json.dumps(stats, ensure_ascii=False)}")
        return stats
    finally:
        # Garante release do lock mesmo se houver exception
        if not bootstrap and not dry_run:
            _release_lock()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Imprime sem enviar")
    ap.add_argument("--bootstrap", action="store_true", help="Marca backlog como enviado sem disparar (1ª vez)")
    args = ap.parse_args()
    executar(dry_run=args.dry_run, bootstrap=args.bootstrap)
