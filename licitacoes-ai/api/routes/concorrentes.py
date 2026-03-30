"""Rotas de concorrentes — v2 com busca PNCP, histórico e perfil."""
import json
import logging
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.deps import get_connection
from shared.database import upsert_concorrente, get_lances_por_cnpj
from config.settings import PNCP_BASE_URL

log = logging.getLogger("concorrentes_v2")
router = APIRouter(prefix="/api/concorrentes", tags=["concorrentes"])


class ConcorrenteCreate(BaseModel):
    cnpj: str
    razao_social: str = ""
    nome_fantasia: str = ""
    segmentos: list[str] = []
    notas: str = ""


@router.get("")
def listar():
    """Retorna concorrentes do banco + fallback config, com stats do histórico."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM concorrentes WHERE ativo = 1").fetchall()
    result = []

    if rows:
        for r in rows:
            d = dict(r)
            for field in ("segmentos", "uf_atuacao"):
                if d.get(field) and isinstance(d[field], str):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        pass

            cnpj = d.get("cnpj", "")
            if cnpj and cnpj != "PREENCHER":
                lances = get_lances_por_cnpj(cnpj, limit=100)
                total = len(lances)
                vitorias = sum(1 for l in lances if l.get("vencedor"))
                d["lances_total"] = total
                d["vitorias"] = vitorias
                d["taxa_vitoria"] = round(vitorias / total * 100, 1) if total > 0 else 0
                d["desconto_medio"] = 0
                d["lances_mes"] = round(total / max(1, 12), 1)
                if d["taxa_vitoria"] >= 50:
                    d["agressividade"] = "alta"
                elif d["taxa_vitoria"] >= 20:
                    d["agressividade"] = "media"
                else:
                    d["agressividade"] = "baixa"
            else:
                notas = (d.get("notas") or "").lower()
                d["agressividade"] = "alta" if "agressiv" in notas else "media"
                d["lances_total"] = 0
                d["vitorias"] = 0
                d["taxa_vitoria"] = 0
                d["desconto_medio"] = 0
                d["lances_mes"] = 0
            result.append(d)
    else:
        config_path = Path(__file__).parent.parent.parent / "config" / "concorrentes.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            for c in data.get("concorrentes", []):
                notas = (c.get("notas") or "").lower()
                result.append({
                    "cnpj": c.get("cnpj", ""),
                    "nome_fantasia": c.get("nome_fantasia", ""),
                    "razao_social": c.get("razao_social", ""),
                    "segmentos": c.get("segmentos", []),
                    "notas": c.get("notas", ""),
                    "agressividade": "alta" if "agressiv" in notas else "media",
                    "lances_total": 0, "vitorias": 0, "taxa_vitoria": 0,
                    "desconto_medio": 0, "lances_mes": 0,
                })
    return result


@router.post("")
def adicionar(body: ConcorrenteCreate):
    """Adiciona ou atualiza concorrente no banco e no config JSON."""
    cnpj = body.cnpj.strip().replace(".", "").replace("/", "").replace("-", "")
    if len(cnpj) != 14:
        raise HTTPException(400, "CNPJ deve ter 14 dígitos")
    cnpj_fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

    row_id = upsert_concorrente(
        cnpj=cnpj_fmt,
        razao_social=body.razao_social,
        nome_fantasia=body.nome_fantasia,
        segmentos=body.segmentos,
        notas=body.notas,
    )
    _sync_to_config(cnpj_fmt, body)
    return {"id": row_id, "cnpj": cnpj_fmt}


def _sync_to_config(cnpj, body):
    config_path = Path(__file__).parent.parent.parent / "config" / "concorrentes.json"
    data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {"concorrentes": []}
    existing = next((c for c in data["concorrentes"] if c.get("cnpj") == cnpj), None)
    if existing:
        existing.update({k: v for k, v in {"razao_social": body.razao_social, "nome_fantasia": body.nome_fantasia, "segmentos": body.segmentos, "notas": body.notas}.items() if v})
    else:
        data["concorrentes"].append({"cnpj": cnpj, "razao_social": body.razao_social, "nome_fantasia": body.nome_fantasia, "segmentos": body.segmentos, "notas": body.notas})
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.delete("/{cnpj:path}")
def remover(cnpj: str):
    conn = get_connection()
    conn.execute("UPDATE concorrentes SET ativo = 0 WHERE cnpj = ?", (cnpj,))
    conn.commit()
    return {"status": "removido"}


@router.get("/buscar-pncp")
def buscar_pncp(
    termo: str = Query(..., min_length=3),
    segmento: str = Query("limpeza"),
    uf: str = Query("RJ"),
):
    """Busca CNPJs de concorrentes via resultados de licitações no PNCP."""
    import httpx

    encontrados = {}
    termo_lower = termo.lower()

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{PNCP_BASE_URL}/contratacoes/publicacao",
                params={
                    "dataInicial": "20250101", "dataFinal": "20260323",
                    "codigoModalidadeContratacao": 6, "uf": uf,
                    "pagina": 1, "tamanhoPagina": 50,
                },
            )
            if resp.status_code != 200:
                return {"items": [], "total": 0, "nota": "API PNCP indisponível"}
            data = resp.json()
            compras = data if isinstance(data, list) else data.get("data", data.get("content", []))
    except Exception as e:
        return {"items": [], "total": 0, "nota": str(e)}

    for compra in compras[:20]:
        orgao_cnpj = compra.get("orgaoEntidade", {}).get("cnpj", "")
        ano = compra.get("anoCompra", "")
        seq = compra.get("sequencialCompra", "")
        if not orgao_cnpj or not ano or not seq:
            continue
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(f"{PNCP_BASE_URL}/orgaos/{orgao_cnpj}/compras/{ano}/{seq}/resultados")
                if resp.status_code != 200:
                    continue
                resultados = resp.json()
                if not isinstance(resultados, list):
                    continue
                for res in resultados:
                    fornecedor = res.get("niFornecedor", "") or res.get("cnpjFornecedor", "")
                    nome = res.get("nomeRazaoSocialFornecedor", "") or res.get("nomeFornecedor", "")
                    if not fornecedor or not nome:
                        continue
                    if termo_lower in nome.lower():
                        if fornecedor not in encontrados:
                            encontrados[fornecedor] = {"cnpj": fornecedor, "razao_social": nome, "participacoes": 0, "vitorias": 0, "ultimo_valor": None}
                        encontrados[fornecedor]["participacoes"] += 1
                        valor = res.get("valorTotalHomologado") or res.get("valorTotalEstimado")
                        if valor:
                            encontrados[fornecedor]["ultimo_valor"] = valor
        except:
            continue

    items = sorted(encontrados.values(), key=lambda x: x["participacoes"], reverse=True)
    return {"items": items, "total": len(items)}


@router.get("/{cnpj:path}/perfil")
def perfil(cnpj: str):
    """Perfil completo de um concorrente com histórico de lances."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM concorrentes WHERE cnpj = ?", (cnpj,)).fetchone()
    cadastro = dict(row) if row else {"cnpj": cnpj}
    for field in ("segmentos", "uf_atuacao"):
        if cadastro.get(field) and isinstance(cadastro[field], str):
            try:
                cadastro[field] = json.loads(cadastro[field])
            except:
                pass

    lances = get_lances_por_cnpj(cnpj, limit=200)
    total = len(lances)
    vitorias = sum(1 for l in lances if l.get("vencedor"))
    valores = [l.get("valor_lance") or l.get("valor_proposta_final") or 0 for l in lances if (l.get("valor_lance") or l.get("valor_proposta_final"))]

    return {
        **cadastro,
        "historico": {
            "total_participacoes": total,
            "vitorias": vitorias,
            "taxa_vitoria": round(vitorias / total * 100, 1) if total > 0 else 0,
            "valor_medio_lance": round(sum(valores) / len(valores), 2) if valores else 0,
        },
        "lances_recentes": [dict(l) for l in lances[:10]],
    }


@router.post("/seed")
def seed():
    """Importa concorrentes do config JSON para o banco."""
    config_path = Path(__file__).parent.parent.parent / "config" / "concorrentes.json"
    if not config_path.exists():
        raise HTTPException(404, "concorrentes.json não encontrado")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    count = 0
    for c in data.get("concorrentes", []):
        cnpj = c.get("cnpj", "")
        if not cnpj or cnpj == "PREENCHER":
            continue
        upsert_concorrente(cnpj=cnpj, razao_social=c.get("razao_social", ""), nome_fantasia=c.get("nome_fantasia", ""), segmentos=c.get("segmentos", []), notas=c.get("notas", ""))
        count += 1
    return {"importados": count}
