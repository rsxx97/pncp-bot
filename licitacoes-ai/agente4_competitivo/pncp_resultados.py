"""Busca resultados de pregões anteriores no PNCP para inteligência competitiva.

Alimenta base local com:
- Concorrentes: quem participa, quanto cobra, taxa de vitória
- Preços praticados por m², por posto, por tipo de serviço
- Tendências de desconto por segmento
"""
import logging
import time
from datetime import date, timedelta

import httpx

log = logging.getLogger("pncp_resultados")


def buscar_resultados_pncp(
    uf: str = "RJ",
    tipo_servico: str = "limpeza",
    dias_retroativos: int = 180,
    max_resultados: int = 50,
) -> list[dict]:
    """Busca resultados de licitações concluídas no PNCP.

    Retorna lista de dicts com:
    - orgao, objeto, valor_estimado, valor_homologado
    - vencedor (empresa, cnpj, valor)
    - desconto_pct
    """
    hoje = date.today()
    ini = (hoje - timedelta(days=dias_retroativos)).strftime("%Y%m%d")
    fim = hoje.strftime("%Y%m%d")

    KWS_SERVICO = {
        "limpeza": ["limpeza", "conservacao", "asseio", "higienizacao"],
        "vigilancia": ["vigilancia", "seguranca", "patrimonial", "armada"],
        "administrativo": ["apoio administrativo", "recepcao", "portaria", "copeiragem", "secretariado"],
        "facilities": ["facilities", "manutencao predial"],
        "obras": ["obra", "construcao", "reforma", "pavimentacao", "engenharia"],
    }

    keywords = KWS_SERVICO.get(tipo_servico, [tipo_servico])

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    resultados = []

    for mod in [5, 6]:
        pagina = 1
        while pagina <= 5 and len(resultados) < max_resultados:
            try:
                time.sleep(0.5)
                with httpx.Client(timeout=45) as client:
                    resp = client.get(url, params={
                        "dataInicial": ini,
                        "dataFinal": fim,
                        "codigoModalidadeContratacao": mod,
                        "uf": uf,
                        "pagina": pagina,
                        "tamanhoPagina": 50,
                    })
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    itens = data.get("data", [])
                    if not itens:
                        break

                    for it in itens:
                        objeto = (it.get("objetoCompra", "") or "").lower()
                        if not any(k in objeto for k in keywords):
                            continue

                        valor_est = it.get("valorTotalEstimado") or 0
                        if valor_est < 10000:
                            continue

                        orgao = it.get("orgaoEntidade", {})
                        unidade = it.get("unidadeOrgao", {})

                        resultados.append({
                            "cnpj_orgao": orgao.get("cnpj", ""),
                            "orgao": orgao.get("razaoSocial", ""),
                            "objeto": it.get("objetoCompra", ""),
                            "valor_estimado": valor_est,
                            "modalidade": mod,
                            "uf": unidade.get("ufSigla", uf),
                            "municipio": unidade.get("municipioNome", ""),
                            "data_publicacao": it.get("dataPublicacaoPncp"),
                            "data_encerramento": it.get("dataEncerramentoProposta"),
                            "ano_compra": it.get("anoCompra"),
                            "seq_compra": it.get("sequencialCompra"),
                            "tipo_servico": tipo_servico,
                        })

                    if pagina >= data.get("totalPaginas", 1):
                        break
                    pagina += 1

            except Exception as e:
                log.warning(f"Erro busca resultados mod {mod} pag {pagina}: {e}")
                break

    log.info(f"Resultados {tipo_servico} {uf}: {len(resultados)} licitações")
    return resultados


def salvar_resultados_banco(resultados: list[dict]):
    """Salva resultados na tabela de inteligência competitiva."""
    from shared.database import get_db

    db = get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS intel_competitiva (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj_orgao TEXT,
        orgao TEXT,
        objeto TEXT,
        valor_estimado REAL,
        valor_homologado REAL,
        desconto_pct REAL,
        vencedor_nome TEXT,
        vencedor_cnpj TEXT,
        vencedor_valor REAL,
        tipo_servico TEXT,
        uf TEXT,
        municipio TEXT,
        modalidade INTEGER,
        data_publicacao TEXT,
        data_encerramento TEXT,
        ano_compra TEXT,
        seq_compra TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    count = 0
    for r in resultados:
        existing = db.execute(
            "SELECT id FROM intel_competitiva WHERE cnpj_orgao = ? AND ano_compra = ? AND seq_compra = ?",
            (r["cnpj_orgao"], r.get("ano_compra"), r.get("seq_compra"))
        ).fetchone()
        if existing:
            continue

        db.execute("""INSERT INTO intel_competitiva
            (cnpj_orgao, orgao, objeto, valor_estimado, tipo_servico, uf, municipio,
             modalidade, data_publicacao, data_encerramento, ano_compra, seq_compra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["cnpj_orgao"], r["orgao"], r["objeto"], r["valor_estimado"],
             r["tipo_servico"], r["uf"], r["municipio"], r["modalidade"],
             r["data_publicacao"], r["data_encerramento"],
             r.get("ano_compra"), r.get("seq_compra")))
        count += 1

    db.commit()
    log.info(f"Salvos: {count} novos resultados")
    return count


def consultar_precos_praticados(tipo_servico: str = "limpeza", uf: str = "RJ") -> dict:
    """Consulta preços praticados na base local de inteligência competitiva."""
    from shared.database import get_db

    db = get_db()
    rows = db.execute("""
        SELECT valor_estimado, vencedor_valor, desconto_pct, vencedor_nome, orgao, municipio
        FROM intel_competitiva
        WHERE tipo_servico = ? AND uf = ? AND valor_estimado > 0
        ORDER BY data_publicacao DESC LIMIT 50
    """, (tipo_servico, uf)).fetchall()

    if not rows:
        return {"total": 0, "mensagem": "Sem dados de inteligência competitiva. Execute a busca primeiro."}

    valores = [r["valor_estimado"] for r in rows if r["valor_estimado"]]
    descontos = [r["desconto_pct"] for r in rows if r["desconto_pct"]]
    vencedores = {}

    for r in rows:
        nome = r["vencedor_nome"] or "Desconhecido"
        if nome not in vencedores:
            vencedores[nome] = {"count": 0, "total_valor": 0}
        vencedores[nome]["count"] += 1
        vencedores[nome]["total_valor"] += r.get("vencedor_valor") or 0

    # Top concorrentes
    top = sorted(vencedores.items(), key=lambda x: x[1]["count"], reverse=True)[:10]

    return {
        "total": len(rows),
        "valor_medio": sum(valores) / len(valores) if valores else 0,
        "valor_min": min(valores) if valores else 0,
        "valor_max": max(valores) if valores else 0,
        "desconto_medio": sum(descontos) / len(descontos) if descontos else 0,
        "top_concorrentes": [{"nome": k, "vitorias": v["count"], "valor_total": v["total_valor"]} for k, v in top],
        "tipo_servico": tipo_servico,
        "uf": uf,
    }
