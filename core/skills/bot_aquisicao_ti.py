"""Bot Aquisição TI/Eletrônicos — radar PNCP RJ.

Empresa nova de TI: foco em modalidades acessíveis (dispensa, cotação eletrônica,
pregão ME/EPP exclusivo) até R$ 80k. Sem exigência de atestado.

Canal: TELEGRAM_BOT_TOKEN_AQUISICAO_TI + TELEGRAM_CHAT_AQUISICAO_TI no .env
Dedup: empresas/_compartilhado/data/aquisicao_ti_sent.json
"""
import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
log = logging.getLogger("bot_aquisicao_ti")

SENT_FILE = Path(__file__).parent.parent.parent / "empresas" / "_compartilhado" / "data" / "aquisicao_ti_sent.json"
SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_AQUISICAO_TI") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_AQUISICAO_TI") or os.getenv("TELEGRAM_CHAT_ID")

UFS_AQUISICAO = ["RJ"]
VALOR_MAXIMO = 80_000.0  # ME/EPP exclusivo (Lei 14.133, art. 48)

# Keywords de busca PNCP (TI + Eletrônicos)
KEYWORDS_BUSCA_PNCP = [
    "equipamentos de informática", "equipamento de informática",
    "suprimentos de informática", "material de informática",
    "notebook", "computador", "desktop", "microcomputador",
    "impressora", "monitor", "servidor de rede", "no-break",
    "switch de rede", "roteador", "access point",
    "projetor multimídia", "datashow",
    "equipamento eletrônico", "equipamento de telefonia",
    "telefone ip", "central telefônica",
    "toner", "cartucho de impressora",
    "câmera de segurança", "cftv",
]

# Modalidades aceitas — Fase 1 (empresa nova, sem atestado)
# Aceita Dispensa, Cotação Eletrônica, Pregão Eletrônico (ME/EPP exclusivo até R$ 80k vem do filtro de valor)
MODALIDADES_ACEITAS = (
    "Dispensa", "Dispensa de Licitação",
    "Cotação Eletrônica", "Cotacao Eletronica",
    "Pregão Eletrônico", "Pregão Presencial",
    "Inexigibilidade", "Inexigibilidade de Licitação",
)
MODALIDADES_CONTRATACAO_DIRETA = (
    "Dispensa", "Dispensa de Licitação",
    "Inexigibilidade", "Inexigibilidade de Licitação",
)

# Exclusões — falsos positivos (serviços de TI que exigem atestado, deixar pra fase 2)
EXCLUSOES_AQUISICAO = [
    "desenvolvimento de software", "desenvolvimento de sistema",
    "fábrica de software", "factory de software",
    "consultoria em tecnologia da informação",
    "outsourcing de impressão", "outsourcing de ti",
    "manutenção corretiva e evolutiva",  # tipicamente software
    "manutenção evolutiva",
    "licença de software", "licenciamento de software",
    "software de gestão", "erp",
    # Veículos (caso "computador de bordo" apareça)
    "veículo", "veicular", "caminhão", "viatura",
]


def _eh_falso(objeto: str) -> bool:
    obj = (objeto or "").lower()
    return any(excl in obj for excl in EXCLUSOES_AQUISICAO)


def _cabecalho(modalidade: str) -> str:
    h = "💻 AQUISIÇÃO TI / ELETRÔNICOS\n\n"
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
    shutil.copy(SENT_FILE, bdir / f"aquisicao_ti_sent_{ts}.json")
    backups = sorted(bdir.glob("aquisicao_ti_sent_*.json"))
    for b in backups[:-10]:
        b.unlink(missing_ok=True)


def _save_sent(s: set):
    _backup_sent()
    SENT_FILE.write_text(json.dumps(sorted(s)), encoding="utf-8")


LOCK_FILE = SENT_FILE.parent / "aquisicao_ti.lock"
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
        log.error("TELEGRAM_BOT_TOKEN_AQUISICAO_TI / CHAT não configurados")
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
    """Mensagem única: PDF anexado + caption (texto formatado).
    No Telegram aparece como uma só mensagem com card do PDF e o texto embaixo."""
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
    """1 GET no detalhado com retries; preenche valor/datas/sigiloso."""
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
    for uf_alvo in UFS_AQUISICAO:
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
                        if uf_real not in UFS_AQUISICAO:
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
        log.info("Consultando PNCP search (TI + Eletrônicos, RJ)...")
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
            modal = ed["modalidade"] or ""
            if not any(m.lower() in modal.lower() for m in MODALIDADES_ACEITAS):
                stats["modalidade_invalida"] += 1
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
            log.info(f"Bot AquisicaoTI: {json.dumps(stats, ensure_ascii=False)}")
            return stats

        if dry_run:
            for ed in candidatos:
                stats["enviados"] += 1
            log.info(f"Bot AquisicaoTI: {json.dumps(stats, ensure_ascii=False)}")
            return stats

        for ed in candidatos:
            pncp_id = ed["pncp_id"]
            _enriquecer_edital(ed)
            # Filtro por valor APÓS enriquecimento
            valor = ed.get("valor_estimado") or 0
            if valor > VALOR_MAXIMO and not ed.get("valor_sigiloso"):
                stats["valor_acima"] += 1
                log.info(f"Pulado (valor R$ {valor:,.2f} > R$ {VALOR_MAXIMO:,.0f}): {pncp_id}")
                continue

            modal = ed.get("modalidade") or ""
            msg = _cabecalho(modal) + formatar_edital(ed)

            if enviar_telegram_com_pdf(msg, pncp_id):
                sent.add(pncp_id)
                stats["enviados"] += 1
                gravar_edital(ed, nicho="aquisicao_ti", enviado=True)
                log.info(f"Enviado {ed['uf']}: {pncp_id} ({stats['enviados']} no total)")
                if stats["enviados"] % SAVE_INCREMENTAL_A_CADA == 0:
                    _save_sent(sent)
                    log.info(f"💾 sent.json salvo ({stats['enviados']} editais)")
                time.sleep(5)
            else:
                stats["falhas"] += 1
                time.sleep(1)

        _save_sent(sent)
        log.info(f"Bot AquisicaoTI: {json.dumps(stats, ensure_ascii=False)}")
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
