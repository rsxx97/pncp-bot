"""Absorvedor completo de licitações de vigilância/segurança do PNCP — RJ.

Varre TODO o estado do RJ nos últimos 2 anos:
1. Busca editais de vigilância (Pregão, Concorrência, Dispensa)
2. Baixa planilhas/propostas dos vencedores
3. Extrai composição de custos (salários, encargos, CI, lucro)
4. Mapeia concorrentes (quem ganha, por quanto, quantas vezes)
5. Calcula preço médio por posto/mês
6. Gera síntese de mercado

Zero API. PNCP público + PyMuPDF local.
"""
import argparse
import hashlib
import json
import logging
import re
import sqlite3
import sys
import time
from datetime import date, timedelta, datetime
from pathlib import Path

import httpx

LICITACOES_AI = Path(__file__).parent.parent.parent / "licitacoes-ai"
sys.path.insert(0, str(LICITACOES_AI))
from dotenv import load_dotenv
load_dotenv(LICITACOES_AI / ".env", override=True)

from config.settings import DB_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("absorver_vigilancia")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
PNCP_BASE = "https://pncp.gov.br/api/consulta/v1"
PNCP_V1 = "https://pncp.gov.br/api/pncp/v1"

DATA_DIR = Path(__file__).parent / "data"
PLANILHAS_DIR = DATA_DIR / "planilhas_vigilancia"
PLANILHAS_DIR.mkdir(parents=True, exist_ok=True)
HISTORICO_FILE = DATA_DIR / "vigilancia_absorvidos.json"

KEYWORDS = [
    "vigilância", "vigilancia", "segurança patrimonial", "seguranca patrimonial",
    "vigilância armada", "vigilancia armada", "vigilância desarmada",
    "portaria", "porteiro", "controle de acesso",
    "bombeiro civil", "brigadista", "cftv", "monitoramento",
]

EXCLUSOES = [
    "vigilância sanitária", "vigilancia sanitaria",
    "vigilância ambiental", "vigilancia ambiental",
    "vigilância em saúde", "vigilancia em saude",
    "segurança do trabalho", "seguranca do trabalho",
    "segurança alimentar", "seguranca alimentar",
    "corpo de bombeiros", "brigada militar", "brigada de infantaria",
]

NOMES_PLANILHA = [
    "planilha", "proposta", "custo", "preço", "preco",
    "composição", "composicao", "orçamento", "orcamento",
    "modulo", "módulo", "encargos", "in05", "in 05",
]


def _load_historico() -> set:
    if HISTORICO_FILE.exists():
        return set(json.loads(HISTORICO_FILE.read_text(encoding="utf-8")))
    return set()


def _save_historico(h: set):
    HISTORICO_FILE.write_text(json.dumps(sorted(h)), encoding="utf-8")


def _eh_vigilancia(objeto: str) -> bool:
    obj = objeto.lower()
    if any(e in obj for e in EXCLUSOES):
        return False
    return any(k in obj for k in KEYWORDS)


def _eh_planilha(titulo: str) -> bool:
    t = titulo.lower()
    return any(k in t for k in NOMES_PLANILHA)


def buscar_editais(uf: str, modalidade: int, pagina: int, dias: int = 730) -> list[dict]:
    hoje = date.today()
    inicio = hoje - timedelta(days=dias)
    try:
        r = httpx.get(f"{PNCP_BASE}/contratacoes/publicacao", params={
            "dataInicial": inicio.strftime("%Y%m%d"),
            "dataFinal": hoje.strftime("%Y%m%d"),
            "codigoModalidadeContratacao": modalidade,
            "uf": uf, "pagina": pagina, "tamanhoPagina": 50,
        }, headers=HEADERS, timeout=90)
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception as e:
        log.debug(f"Busca erro: {e}")
    return []


def buscar_arquivos(cnpj: str, ano, seq) -> list[dict]:
    try:
        r = httpx.get(f"{PNCP_V1}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
                      headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
    except Exception:
        pass
    return []


def buscar_resultados_item(cnpj: str, ano, seq, num_item: int) -> list[dict]:
    try:
        r = httpx.get(f"{PNCP_V1}/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{num_item}/resultados",
                      headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
    except Exception:
        pass
    return []


def buscar_itens(cnpj: str, ano, seq) -> list[dict]:
    try:
        r = httpx.get(f"{PNCP_V1}/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
                      headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
    except Exception:
        pass
    return []


def baixar_arquivo(url: str, destino: Path) -> bool:
    try:
        r = httpx.get(url, timeout=60, follow_redirects=True, headers=HEADERS)
        if r.status_code == 200 and len(r.content) > 1000:
            destino.write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


def extrair_dados_pdf(filepath: str) -> dict:
    """Extrai dados de planilha de vigilância de um PDF."""
    dados = {
        "salario_base": None, "periculosidade": None,
        "adicional_noturno": None, "vale_transporte": None,
        "vale_alimentacao": None, "cesta_basica": None,
        "plano_saude": None, "encargos_pct": None,
        "ci_pct": None, "lucro_pct": None,
        "custo_posto_mensal": None, "postos": [],
    }

    try:
        import fitz
        doc = fitz.open(filepath)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception:
        return dados

    if len(text.strip()) < 100:
        return dados

    txt = text.lower()

    # Salário base
    m = re.search(r'sal[aá]rio\s*(?:base|mensal)?\s*[=:R$\s]*([\d.,]+)', txt)
    if m:
        try:
            v = float(m.group(1).replace(".", "").replace(",", "."))
            if 1000 < v < 10000:
                dados["salario_base"] = v
        except Exception:
            pass

    # Periculosidade (30%)
    m = re.search(r'periculosidade\s*[=:(\s]*([\d.,]+)\s*%?', txt)
    if m:
        try:
            v = float(m.group(1).replace(",", "."))
            if v > 1:
                v = v / 100
            dados["periculosidade"] = v
        except Exception:
            pass

    # Adicional noturno
    m = re.search(r'adicional\s*noturno\s*[=:(\s]*([\d.,]+)\s*%?', txt)
    if m:
        try:
            v = float(m.group(1).replace(",", "."))
            if v > 1:
                v = v / 100
            dados["adicional_noturno"] = v
        except Exception:
            pass

    # Vale alimentação
    m = re.search(r'vale\s*(?:alimenta[çc][ãa]o|refei[çc][ãa]o)\s*[=:R$\s]*([\d.,]+)', txt)
    if m:
        try:
            v = float(m.group(1).replace(".", "").replace(",", "."))
            if 5 < v < 2000:
                dados["vale_alimentacao"] = v
        except Exception:
            pass

    # Cesta básica
    m = re.search(r'cesta\s*b[aá]sica\s*[=:R$\s]*([\d.,]+)', txt)
    if m:
        try:
            v = float(m.group(1).replace(".", "").replace(",", "."))
            if 50 < v < 1000:
                dados["cesta_basica"] = v
        except Exception:
            pass

    # Plano saúde
    m = re.search(r'(?:plano|assist[eê]ncia)\s*(?:de\s*)?sa[uú]de\s*[=:R$\s]*([\d.,]+)', txt)
    if m:
        try:
            v = float(m.group(1).replace(".", "").replace(",", "."))
            if 50 < v < 2000:
                dados["plano_saude"] = v
        except Exception:
            pass

    # Encargos sociais
    m = re.search(r'encargos\s*sociais\s*[=:(\s]*([\d.,]+)\s*%', txt)
    if m:
        try:
            v = float(m.group(1).replace(",", "."))
            if v > 1:
                v = v / 100
            if 0.3 < v < 1.2:
                dados["encargos_pct"] = v
        except Exception:
            pass

    # CI (Custos Indiretos)
    m = re.search(r'(?:custos?\s*indiretos?|ci)\s*[=:(\s]*([\d.,]+)\s*%', txt)
    if m:
        try:
            v = float(m.group(1).replace(",", "."))
            if v > 1:
                v = v / 100
            if 0.01 < v < 0.15:
                dados["ci_pct"] = v
        except Exception:
            pass

    # Lucro
    m = re.search(r'lucro\s*[=:(\s]*([\d.,]+)\s*%', txt)
    if m:
        try:
            v = float(m.group(1).replace(",", "."))
            if v > 1:
                v = v / 100
            if 0.01 < v < 0.20:
                dados["lucro_pct"] = v
        except Exception:
            pass

    # Valor total do posto/mês
    for padrao in [
        r'(?:valor|custo|pre[çc]o)\s*(?:total|mensal|do\s*posto)\s*[=:R$\s]*([\d.,]+)',
        r'total\s*(?:mensal|do\s*posto|geral)\s*[=:R$\s]*([\d.,]+)',
    ]:
        m = re.search(padrao, txt)
        if m:
            try:
                v = float(m.group(1).replace(".", "").replace(",", "."))
                if 3000 < v < 30000:
                    dados["custo_posto_mensal"] = v
                    break
            except Exception:
                pass

    return dados


def absorver(max_paginas: int = 20, dias: int = 730) -> dict:
    """Absorve TUDO de vigilância RJ dos últimos 2 anos."""
    historico = _load_historico()
    stats = {
        "editais_varridos": 0, "editais_vigilancia": 0,
        "com_resultado": 0, "planilhas_baixadas": 0,
        "concorrentes": 0, "ja_processados": 0, "erros": 0,
    }

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    modalidades = [5, 6, 8, 9]  # Concorrência, Pregão, Dispensa, Inexigibilidade

    for modalidade in modalidades:
        for pagina in range(1, max_paginas + 1):
            editais = buscar_editais("RJ", modalidade, pagina, dias)
            if not editais:
                break

            for ed in editais:
                stats["editais_varridos"] += 1
                objeto = ed.get("objetoCompra", "")

                if not _eh_vigilancia(objeto):
                    continue

                stats["editais_vigilancia"] += 1
                orgao = ed.get("orgaoEntidade", {})
                cnpj_orgao = orgao.get("cnpj", "")
                ano = ed.get("anoCompra", "")
                seq = ed.get("sequencialCompra", "")

                if not (cnpj_orgao and ano and seq):
                    continue

                uid = f"{cnpj_orgao}-{ano}-{seq}"
                if uid in historico:
                    stats["ja_processados"] += 1
                    continue

                valor_ref = ed.get("valorTotalEstimado", 0)
                orgao_nome = orgao.get("razaoSocial", "")

                # === BUSCA ARQUIVOS (planilhas dos vencedores) ===
                arquivos = buscar_arquivos(cnpj_orgao, ano, seq)
                for arq in arquivos:
                    titulo = arq.get("titulo") or ""
                    seq_doc = arq.get("sequencialDocumento", "")

                    if _eh_planilha(titulo):
                        url_download = f"{PNCP_V1}/orgaos/{cnpj_orgao}/compras/{ano}/{seq}/arquivos/{seq_doc}"
                        ext = ".pdf"
                        if any(titulo.lower().endswith(e) for e in (".xlsx", ".xls")):
                            ext = ".xlsx"

                        nome_safe = re.sub(r'[^\w\-.]', '_', titulo)[:60]
                        destino = PLANILHAS_DIR / f"RJ_{cnpj_orgao}_{ano}_{seq}_{nome_safe}{ext}"

                        if not destino.exists():
                            if baixar_arquivo(url_download, destino):
                                stats["planilhas_baixadas"] += 1
                                log.info(f"Planilha: {destino.name[:60]} | {orgao_nome[:30]}")

                                # Extrai dados se for PDF
                                if ext == ".pdf":
                                    dados = extrair_dados_pdf(str(destino))
                                    if dados.get("custo_posto_mensal") or dados.get("salario_base"):
                                        log.info(f"  Extraído: sal={dados.get('salario_base')} | posto={dados.get('custo_posto_mensal')} | lucro={dados.get('lucro_pct')}")

                # === BUSCA RESULTADOS (quem ganhou) ===
                itens = buscar_itens(cnpj_orgao, ano, seq)
                for it in itens:
                    num_item = it.get("numeroItem", 1)
                    resultados = buscar_resultados_item(cnpj_orgao, ano, seq, num_item)

                    for res in resultados:
                        posicao = res.get("ordenClassificacao", 0)
                        nome_venc = res.get("nomeRazaoSocialFornecedor", "")
                        cnpj_venc = (res.get("niFornecedor", "")).replace(".", "").replace("/", "").replace("-", "")
                        valor_hom = res.get("valorTotalHomologado", 0)

                        if not nome_venc:
                            continue

                        stats["com_resultado"] += 1

                        # Calcula desconto
                        desconto = 0
                        if valor_ref and valor_hom and valor_ref > 0:
                            desconto = round((1 - valor_hom / valor_ref) * 100, 2)

                        # Registra vencedor (posição 1)
                        if posicao == 1 and cnpj_venc:
                            existing = conn.execute(
                                "SELECT id, vitorias, valor_total_ganho FROM concorrentes_vigilancia WHERE cnpj=?",
                                (cnpj_venc,)
                            ).fetchone()

                            if existing:
                                conn.execute("""
                                    UPDATE concorrentes_vigilancia
                                    SET vitorias = vitorias + 1,
                                        valor_total_ganho = valor_total_ganho + ?,
                                        desconto_medio_pct = (COALESCE(desconto_medio_pct,0) * vitorias + ?) / (vitorias + 1),
                                        ultimo_contrato = ?,
                                        updated_at = datetime('now')
                                    WHERE cnpj = ?
                                """, (valor_hom or 0, desconto, uid, cnpj_venc))
                            else:
                                conn.execute("""
                                    INSERT INTO concorrentes_vigilancia
                                    (cnpj, razao_social, uf, vitorias, valor_total_ganho,
                                     desconto_medio_pct, ultimo_contrato)
                                    VALUES (?, ?, 'RJ', 1, ?, ?, ?)
                                """, (cnpj_venc, nome_venc, valor_hom or 0, desconto, uid))
                            stats["concorrentes"] += 1

                            # Registra na planilhas_referencia
                            conn.execute("""
                                INSERT OR IGNORE INTO planilhas_referencia
                                (pncp_id, orgao, objeto, uf, tipo_obra, valor_homologado,
                                 valor_referencia, desconto_pct, nome_vencedor, cnpj_vencedor,
                                 fonte, data_homologacao)
                                VALUES (?, ?, ?, 'RJ', 'vigilancia', ?, ?, ?, ?, ?, 'pncp', ?)
                            """, (
                                uid, orgao_nome[:100], objeto[:200],
                                valor_hom, valor_ref, desconto,
                                nome_venc, cnpj_venc,
                                ed.get("dataPublicacaoPncp", ""),
                            ))

                            log.info(f"Vencedor: {nome_venc[:35]} | R$ {valor_hom:,.0f} | Desc {desconto:.1f}% | {orgao_nome[:25]}")

                historico.add(uid)
                time.sleep(0.6)

            log.info(f"[RJ] mod={modalidade} p{pagina}: {len(editais)} editais, {stats['editais_vigilancia']} vigilância, {stats['com_resultado']} resultados")

            if len(editais) < 50:
                break
            time.sleep(0.3)

    conn.commit()
    conn.close()
    _save_historico(historico)
    log.info(f"Absorção completa: {json.dumps(stats, ensure_ascii=False)}")
    return stats


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser(description="Absorvedor de vigilância PNCP — RJ completo")
    ap.add_argument("--paginas", type=int, default=20, help="Páginas por modalidade")
    ap.add_argument("--dias", type=int, default=730, help="Dias retroativos")
    args = ap.parse_args()

    # Cria tabelas primeiro
    from skill_vigilancia import criar_tabelas, popular_cbos, popular_equipamentos, popular_cct_rj, gerar_sintese
    criar_tabelas()
    popular_cbos()
    popular_equipamentos()
    popular_cct_rj()

    # Absorve
    stats = absorver(max_paginas=args.paginas, dias=args.dias)
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    # Síntese
    gerar_sintese()
