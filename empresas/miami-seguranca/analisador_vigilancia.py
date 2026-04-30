"""Analisador completo de licitações de vigilância — RJ.

Para CADA licitação de vigilância:
1. Pega TODOS os participantes (não só vencedor)
2. Compara preço de cada um vs referência
3. Analisa POR QUE ganhou (menor preço em quê?)
4. Analisa POR QUE perdeu (onde errou o preço?)
5. Extrai composição das planilhas (salário, encargos, CI, lucro)
6. Gera relatório por licitação
7. Consolida lições aprendidas

Zero API. PNCP público + PyMuPDF.
"""
import argparse
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
log = logging.getLogger("analisador_vigilancia")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
PNCP_BASE = "https://pncp.gov.br/api/consulta/v1"
PNCP_V1 = "https://pncp.gov.br/api/pncp/v1"

DATA_DIR = Path(__file__).parent / "data"
PLANILHAS_DIR = DATA_DIR / "planilhas_vigilancia"
RELATORIOS_DIR = DATA_DIR / "relatorios"
PLANILHAS_DIR.mkdir(parents=True, exist_ok=True)
RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
HISTORICO_FILE = DATA_DIR / "analise_historico.json"

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
    "corpo de bombeiros", "brigada militar",
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

def _eh_vigilancia(obj: str) -> bool:
    o = obj.lower()
    if any(e in o for e in EXCLUSOES):
        return False
    return any(k in o for k in KEYWORDS)


def criar_tabelas():
    """Cria tabelas de análise detalhada."""
    conn = sqlite3.connect(DB_PATH)

    # Participantes de cada licitação (TODOS, não só vencedor)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS participantes_licitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pncp_id TEXT NOT NULL,
            cnpj TEXT,
            razao_social TEXT,
            posicao INTEGER,
            valor_proposta REAL,
            valor_referencia REAL,
            desconto_pct REAL,
            situacao TEXT,
            motivo_desclassificacao TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Relatório de análise por licitação
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analise_licitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pncp_id TEXT NOT NULL UNIQUE,
            orgao TEXT,
            objeto TEXT,
            uf TEXT,
            valor_referencia REAL,
            valor_vencedor REAL,
            desconto_vencedor_pct REAL,
            total_participantes INTEGER,
            total_desclassificados INTEGER,
            diferenca_1o_2o REAL,
            diferenca_1o_2o_pct REAL,
            margem_competitiva REAL,
            cnpj_vencedor TEXT,
            nome_vencedor TEXT,
            motivo_vitoria TEXT,
            padrao_precos TEXT,
            licao_aprendida TEXT,
            salario_extraido REAL,
            encargos_extraido REAL,
            ci_extraido REAL,
            lucro_extraido REAL,
            custo_posto_extraido REAL,
            planilha_path TEXT,
            data_resultado TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    log.info("Tabelas de análise criadas")


def extrair_dados_pdf(filepath: str) -> dict:
    """Extrai composição de custos de planilha PDF de vigilância."""
    dados = {
        "salario_base": None, "periculosidade": None,
        "adicional_noturno": None, "vale_alimentacao": None,
        "cesta_basica": None, "plano_saude": None,
        "encargos_pct": None, "ci_pct": None, "lucro_pct": None,
        "custo_posto_mensal": None, "texto_resumo": "",
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
    dados["texto_resumo"] = txt[:500]

    patterns = {
        "salario_base": (r'sal[aá]rio\s*(?:base|mensal|normativo)?\s*[=:R$\s]*([\d.,]+)', 1000, 10000),
        "periculosidade": (r'periculosidade\s*[=:(\s]*([\d.,]+)\s*%?', 0, 100),
        "adicional_noturno": (r'adicional\s*noturno\s*[=:(\s]*([\d.,]+)\s*%?', 0, 100),
        "vale_alimentacao": (r'vale\s*(?:alimenta[çc][ãa]o|refei[çc][ãa]o)\s*[=:R$\s]*([\d.,]+)', 5, 2000),
        "cesta_basica": (r'cesta\s*b[aá]sica\s*[=:R$\s]*([\d.,]+)', 50, 1000),
        "plano_saude": (r'(?:plano|assist[eê]ncia)\s*(?:de\s*)?sa[uú]de\s*[=:R$\s]*([\d.,]+)', 50, 2000),
        "encargos_pct": (r'encargos\s*sociais\s*[=:(\s]*([\d.,]+)\s*%', 30, 120),
        "ci_pct": (r'(?:custos?\s*indiretos?|ci)\s*[=:(\s]*([\d.,]+)\s*%', 1, 15),
        "lucro_pct": (r'lucro\s*[=:(\s]*([\d.,]+)\s*%', 1, 20),
        "custo_posto_mensal": (r'(?:valor|custo|pre[çc]o)\s*(?:total|mensal|do\s*posto)\s*[=:R$\s]*([\d.,]+)', 3000, 30000),
    }

    for campo, (padrao, vmin, vmax) in patterns.items():
        m = re.search(padrao, txt)
        if m:
            try:
                v = float(m.group(1).replace(".", "").replace(",", "."))
                # Campos percentuais
                if campo in ("periculosidade", "adicional_noturno", "encargos_pct", "ci_pct", "lucro_pct"):
                    if v > 1 and campo not in ("encargos_pct",):
                        v = v / 100
                if vmin <= (v * 100 if v < 1 and campo.endswith("_pct") else v) <= vmax or vmin <= v <= vmax:
                    dados[campo] = v
            except Exception:
                pass

    return dados


def analisar_licitacao(cnpj_orgao: str, ano: str, seq: str, objeto: str,
                       orgao_nome: str, valor_ref: float, conn) -> dict:
    """Analisa UMA licitação completa — todos participantes + planilhas."""
    uid = f"{cnpj_orgao}-{ano}-{seq}"
    resultado = {
        "pncp_id": uid, "orgao": orgao_nome, "objeto": objeto,
        "valor_referencia": valor_ref,
        "participantes": [], "vencedor": None,
        "planilhas_baixadas": 0, "dados_extraidos": {},
    }

    # 1. Busca ITENS
    try:
        r = httpx.get(f"{PNCP_V1}/orgaos/{cnpj_orgao}/compras/{ano}/{seq}/itens",
                      headers=HEADERS, timeout=30)
        itens = []
        if r.status_code == 200:
            data = r.json()
            itens = data if isinstance(data, list) else data.get("data", [])
    except Exception:
        itens = []

    # 2. Para cada item, busca TODOS os participantes
    todos_participantes = []
    for it in itens:
        num_item = it.get("numeroItem", 1)
        try:
            r = httpx.get(
                f"{PNCP_V1}/orgaos/{cnpj_orgao}/compras/{ano}/{seq}/itens/{num_item}/resultados",
                headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                participantes = data if isinstance(data, list) else data.get("data", [])
                for p in participantes:
                    nome = p.get("nomeRazaoSocialFornecedor", "")
                    cnpj_part = (p.get("niFornecedor", "")).replace(".", "").replace("/", "").replace("-", "")
                    posicao = p.get("ordenClassificacao", 0)
                    valor = p.get("valorTotalHomologado", p.get("valorTotal", 0))
                    situacao = p.get("situacaoCompraItemResultado", {})
                    sit_desc = situacao.get("descricao", "") if isinstance(situacao, dict) else str(situacao)

                    desconto = 0
                    if valor_ref and valor and valor_ref > 0:
                        desconto = round((1 - valor / valor_ref) * 100, 2)

                    part = {
                        "cnpj": cnpj_part, "razao_social": nome,
                        "posicao": posicao, "valor": valor,
                        "desconto_pct": desconto, "situacao": sit_desc,
                    }
                    todos_participantes.append(part)

                    # Salva no banco
                    conn.execute("""
                        INSERT OR IGNORE INTO participantes_licitacao
                        (pncp_id, cnpj, razao_social, posicao, valor_proposta,
                         valor_referencia, desconto_pct, situacao)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (uid, cnpj_part, nome, posicao, valor, valor_ref, desconto, sit_desc))

        except Exception:
            pass
        time.sleep(0.3)

    resultado["participantes"] = sorted(todos_participantes, key=lambda x: x.get("posicao", 999))

    # 3. Busca ARQUIVOS (planilhas)
    try:
        r = httpx.get(f"{PNCP_V1}/orgaos/{cnpj_orgao}/compras/{ano}/{seq}/arquivos",
                      headers=HEADERS, timeout=30)
        arquivos = []
        if r.status_code == 200:
            data = r.json()
            arquivos = data if isinstance(data, list) else data.get("data", [])
    except Exception:
        arquivos = []

    planilha_path = ""
    for arq in arquivos:
        titulo = arq.get("titulo", "")
        seq_doc = arq.get("sequencialDocumento", "")
        if any(k in titulo.lower() for k in NOMES_PLANILHA):
            ext = ".pdf"
            if any(titulo.lower().endswith(e) for e in (".xlsx", ".xls")):
                ext = ".xlsx"
            nome_safe = re.sub(r'[^\w\-.]', '_', titulo)[:60]
            destino = PLANILHAS_DIR / f"RJ_{cnpj_orgao}_{ano}_{seq}_{nome_safe}{ext}"

            if not destino.exists():
                url = f"{PNCP_V1}/orgaos/{cnpj_orgao}/compras/{ano}/{seq}/arquivos/{seq_doc}"
                try:
                    r2 = httpx.get(url, timeout=60, follow_redirects=True, headers=HEADERS)
                    if r2.status_code == 200 and len(r2.content) > 1000:
                        destino.write_bytes(r2.content)
                        resultado["planilhas_baixadas"] += 1
                        planilha_path = str(destino)
                except Exception:
                    pass
            else:
                planilha_path = str(destino)

            # Extrai dados
            if destino.exists() and str(destino).endswith(".pdf"):
                dados = extrair_dados_pdf(str(destino))
                if any(v for v in dados.values() if v and v != ""):
                    resultado["dados_extraidos"] = dados

    # 4. ANÁLISE — por que ganhou, por que perdeu
    vencedor = None
    segundo = None
    desclassificados = 0
    motivos_desclass = []

    for p in resultado["participantes"]:
        if p["posicao"] == 1:
            vencedor = p
        elif p["posicao"] == 2:
            segundo = p
        if "desclass" in (p.get("situacao", "") or "").lower():
            desclassificados += 1
            motivos_desclass.append(f"{p['razao_social'][:30]}: {p.get('situacao','')[:50]}")

    resultado["vencedor"] = vencedor

    # Gera análise
    motivo_vitoria = ""
    licao = ""
    margem = 0

    if vencedor:
        if segundo:
            margem = round(segundo["valor"] - vencedor["valor"], 2)
            margem_pct = round(margem / vencedor["valor"] * 100, 2) if vencedor["valor"] else 0

            if margem_pct < 2:
                motivo_vitoria = f"Venceu por margem apertada ({margem_pct:.1f}% / R$ {margem:,.0f} abaixo do 2o)"
                licao = "Disputa acirrada — preço muito próximo. Qualquer centavo conta."
            elif margem_pct < 10:
                motivo_vitoria = f"Venceu com desconto moderado ({margem_pct:.1f}% abaixo do 2o)"
                licao = "Preço competitivo. Desconto entre 2-10% sobre o segundo colocado."
            else:
                motivo_vitoria = f"Venceu folgado ({margem_pct:.1f}% abaixo do 2o)"
                licao = "Vencedor com preço muito abaixo — pode estar com margem apertada ou erro."
        else:
            motivo_vitoria = "Único participante classificado"
            licao = "Sem concorrência real — oportunidade de margem maior."

        if desclassificados:
            motivo_vitoria += f". {desclassificados} desclassificado(s)"
            licao += f" Atenção: {desclassificados} desclassificados — verificar motivos."

    # Padrão de preços
    valores = [p["valor"] for p in resultado["participantes"] if p.get("valor", 0) > 0]
    padrao = ""
    if len(valores) >= 2:
        media = sum(valores) / len(valores)
        amplitude = max(valores) - min(valores)
        amplitude_pct = round(amplitude / media * 100, 1) if media else 0
        padrao = f"Amplitude: {amplitude_pct}% | Média: R$ {media:,.0f} | {len(valores)} propostas"

    # Salva análise no banco
    dados_ext = resultado.get("dados_extraidos", {})
    try:
        conn.execute("""
            INSERT OR REPLACE INTO analise_licitacao
            (pncp_id, orgao, objeto, uf, valor_referencia, valor_vencedor,
             desconto_vencedor_pct, total_participantes, total_desclassificados,
             diferenca_1o_2o, diferenca_1o_2o_pct, margem_competitiva,
             cnpj_vencedor, nome_vencedor, motivo_vitoria, padrao_precos,
             licao_aprendida, salario_extraido, encargos_extraido,
             ci_extraido, lucro_extraido, custo_posto_extraido,
             planilha_path, data_resultado)
            VALUES (?, ?, ?, 'RJ', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uid, orgao_nome[:100], objeto[:200], valor_ref,
            vencedor["valor"] if vencedor else None,
            vencedor["desconto_pct"] if vencedor else None,
            len(resultado["participantes"]), desclassificados,
            margem, round(margem / vencedor["valor"] * 100, 2) if vencedor and vencedor["valor"] else None,
            margem,
            vencedor["cnpj"] if vencedor else None,
            vencedor["razao_social"] if vencedor else None,
            motivo_vitoria, padrao, licao,
            dados_ext.get("salario_base"), dados_ext.get("encargos_pct"),
            dados_ext.get("ci_pct"), dados_ext.get("lucro_pct"),
            dados_ext.get("custo_posto_mensal"),
            planilha_path, datetime.now().isoformat(),
        ))
    except Exception as e:
        log.warning(f"Erro salvar análise {uid}: {e}")

    # Registra concorrente vencedor
    if vencedor and vencedor.get("cnpj"):
        existing = conn.execute(
            "SELECT id FROM concorrentes_vigilancia WHERE cnpj=?",
            (vencedor["cnpj"],)
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE concorrentes_vigilancia
                SET vitorias = vitorias + 1,
                    valor_total_ganho = valor_total_ganho + ?,
                    updated_at = datetime('now')
                WHERE cnpj = ?
            """, (vencedor["valor"] or 0, vencedor["cnpj"]))
        else:
            conn.execute("""
                INSERT INTO concorrentes_vigilancia
                (cnpj, razao_social, uf, vitorias, valor_total_ganho)
                VALUES (?, ?, 'RJ', 1, ?)
            """, (vencedor["cnpj"], vencedor["razao_social"], vencedor["valor"] or 0))

    # Log detalhado
    n_part = len(resultado["participantes"])
    if vencedor:
        log.info(f"ANÁLISE {uid}: {orgao_nome[:25]} | {n_part} participantes | Vencedor: {vencedor['razao_social'][:25]} R$ {vencedor['valor']:,.0f} (desc {vencedor['desconto_pct']:.1f}%) | {motivo_vitoria[:50]}")
    else:
        log.info(f"ANÁLISE {uid}: {orgao_nome[:25]} | Sem resultado")

    return resultado


def executar(max_paginas: int = 20, dias: int = 730) -> dict:
    """Varre TODO o RJ, analisa cada licitação de vigilância."""
    historico = _load_historico()
    stats = {
        "editais_varridos": 0, "editais_vigilancia": 0,
        "analisados": 0, "com_participantes": 0,
        "planilhas_baixadas": 0, "ja_processados": 0, "erros": 0,
    }

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    hoje = date.today()
    modalidades = [5, 6, 8]

    # Divide em blocos de 180 dias (PNCP não aceita range > 1 ano)
    blocos = []
    d = hoje
    while (hoje - d).days < dias:
        bloco_fim = d
        bloco_inicio = d - timedelta(days=180)
        if (hoje - bloco_inicio).days > dias:
            bloco_inicio = hoje - timedelta(days=dias)
        blocos.append((bloco_inicio, bloco_fim))
        d = bloco_inicio - timedelta(days=1)

    for modalidade in modalidades:
        for bloco_inicio, bloco_fim in blocos:
            for pagina in range(1, max_paginas + 1):
                try:
                    r = httpx.get(f"{PNCP_BASE}/contratacoes/publicacao", params={
                        "dataInicial": bloco_inicio.strftime("%Y%m%d"),
                        "dataFinal": bloco_fim.strftime("%Y%m%d"),
                        "codigoModalidadeContratacao": modalidade,
                        "uf": "RJ", "pagina": pagina, "tamanhoPagina": 50,
                    }, headers=HEADERS, timeout=90)

                    if r.status_code != 200:
                        log.warning(f"PNCP {r.status_code} mod={modalidade} {bloco_inicio}→{bloco_fim} p{pagina}")
                        break
                    editais = r.json().get("data", [])
                    if not editais:
                        break

                    for ed in editais:
                        stats["editais_varridos"] += 1
                        objeto = ed.get("objetoCompra", "")

                        if not _eh_vigilancia(objeto):
                            continue

                        stats["editais_vigilancia"] += 1
                        orgao = ed.get("orgaoEntidade", {})
                        cnpj = orgao.get("cnpj", "")
                        ano = ed.get("anoCompra", "")
                        seq = ed.get("sequencialCompra", "")

                        if not (cnpj and ano and seq):
                            continue

                        uid = f"{cnpj}-{ano}-{seq}"
                        if uid in historico:
                            stats["ja_processados"] += 1
                            continue

                        valor_ref = ed.get("valorTotalEstimado", 0)
                        orgao_nome = orgao.get("razaoSocial", "")

                        try:
                            resultado = analisar_licitacao(
                                cnpj, str(ano), str(seq), objeto,
                                orgao_nome, valor_ref, conn
                            )
                            stats["analisados"] += 1
                            if resultado["participantes"]:
                                stats["com_participantes"] += 1
                            stats["planilhas_baixadas"] += resultado["planilhas_baixadas"]
                        except Exception as e:
                            stats["erros"] += 1
                            log.warning(f"Erro análise {uid}: {e}")

                        historico.add(uid)
                        conn.commit()
                        time.sleep(0.8)

                    log.info(f"[RJ] mod={modalidade} {bloco_inicio}→{bloco_fim} p{pagina}: {len(editais)} editais | {stats['analisados']} analisados | {stats['com_participantes']} com participantes")

                    if len(editais) < 50:
                        break
                    time.sleep(0.3)

                except Exception as e:
                    stats["erros"] += 1
                    log.warning(f"Erro busca mod={modalidade} p={pagina}: {e}")
                    break

    conn.commit()
    conn.close()
    _save_historico(historico)
    log.info(f"Análise completa: {json.dumps(stats, ensure_ascii=False)}")
    return stats


def gerar_relatorio_mercado():
    """Gera relatório completo do mercado de vigilância RJ."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print()
    print("═" * 65)
    print("  RELATÓRIO DE MERCADO — VIGILÂNCIA RJ")
    print("  Skill.Vigilância — Análise Completa")
    print("═" * 65)

    # Licitações analisadas
    r = conn.execute("""
        SELECT COUNT(*), AVG(valor_vencedor), AVG(desconto_vencedor_pct),
               AVG(total_participantes), AVG(diferenca_1o_2o_pct),
               SUM(valor_vencedor)
        FROM analise_licitacao WHERE valor_vencedor > 0
    """).fetchone()
    print(f"\n  LICITAÇÕES ANALISADAS: {r[0]}")
    if r[0]:
        print(f"    Valor médio vencedor: R$ {r[1]:,.2f}")
        print(f"    Desconto médio: {r[2]:.1f}%")
        print(f"    Participantes médio: {r[3]:.1f}")
        print(f"    Margem 1º→2º: {r[4] or 0:.1f}%")
        print(f"    Volume total: R$ {r[5]:,.2f}")

    # Padrão de vitória
    print(f"\n  PADRÃO DE VITÓRIA:")
    vitorias = conn.execute("""
        SELECT motivo_vitoria, COUNT(*)
        FROM analise_licitacao
        WHERE motivo_vitoria IS NOT NULL AND motivo_vitoria != ''
        GROUP BY motivo_vitoria ORDER BY COUNT(*) DESC LIMIT 10
    """).fetchall()
    for v in vitorias:
        print(f"    {v[1]:>3}x | {v[0][:70]}")

    # Lições aprendidas
    print(f"\n  LIÇÕES APRENDIDAS:")
    licoes = conn.execute("""
        SELECT licao_aprendida, COUNT(*)
        FROM analise_licitacao
        WHERE licao_aprendida IS NOT NULL AND licao_aprendida != ''
        GROUP BY licao_aprendida ORDER BY COUNT(*) DESC LIMIT 10
    """).fetchall()
    for l in licoes:
        print(f"    {l[1]:>3}x | {l[0][:70]}")

    # Top concorrentes
    print(f"\n  TOP 15 CONCORRENTES:")
    rows = conn.execute("""
        SELECT razao_social, cnpj, vitorias, valor_total_ganho
        FROM concorrentes_vigilancia
        ORDER BY vitorias DESC LIMIT 15
    """).fetchall()
    for i, r in enumerate(rows, 1):
        print(f"    {i:>2}. {r['razao_social'][:40]:40s} | {r['vitorias']:>3} vitórias | R$ {r['valor_total_ganho']:>14,.2f}")

    # Composição de custos extraída
    r2 = conn.execute("""
        SELECT AVG(salario_extraido), AVG(encargos_extraido),
               AVG(ci_extraido), AVG(lucro_extraido), AVG(custo_posto_extraido),
               COUNT(CASE WHEN salario_extraido > 0 THEN 1 END)
        FROM analise_licitacao
    """).fetchone()
    if r2[5]:
        print(f"\n  COMPOSIÇÃO MÉDIA (extraída de {r2[5]} planilhas):")
        if r2[0]: print(f"    Salário base: R$ {r2[0]:,.2f}")
        if r2[1]: print(f"    Encargos: {r2[1]*100:.1f}%")
        if r2[2]: print(f"    CI: {r2[2]*100:.1f}%")
        if r2[3]: print(f"    Lucro: {r2[3]*100:.1f}%")
        if r2[4]: print(f"    Custo posto/mês: R$ {r2[4]:,.2f}")

    # Participantes totais
    total_part = conn.execute("SELECT COUNT(DISTINCT cnpj) FROM participantes_licitacao").fetchone()[0]
    print(f"\n  EMPRESAS MAPEADAS: {total_part}")

    print("═" * 65)
    conn.close()


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser(description="Analisador completo de vigilância RJ")
    ap.add_argument("--paginas", type=int, default=20, help="Páginas por modalidade")
    ap.add_argument("--dias", type=int, default=730, help="Dias retroativos")
    ap.add_argument("--relatorio", action="store_true", help="Só gera relatório")
    args = ap.parse_args()

    # Cria tabelas
    criar_tabelas()
    from skill_vigilancia import criar_tabelas as ct2, popular_cbos, popular_equipamentos, popular_cct_rj
    ct2()
    popular_cbos()
    popular_equipamentos()
    popular_cct_rj()

    if args.relatorio:
        gerar_relatorio_mercado()
    else:
        stats = executar(max_paginas=args.paginas, dias=args.dias)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        gerar_relatorio_mercado()
