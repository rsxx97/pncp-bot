import json
import re
import requests
from flask import Flask, render_template, request, jsonify
from database import (init_db, listar_oportunidades, atualizar_status, toggle_favorito,
                      salvar_notas, estatisticas, relatorios, inserir_acompanhamento,
                      listar_acompanhamentos, buscar_acompanhamento,
                      remover_acompanhamento, salvar_notas_acompanhamento,
                      listar_comentarios, adicionar_comentario, remover_comentario,
                      contar_comentarios, contar_comentarios_batch,
                      contar_nao_lidos_batch)

PNCP_BASE = "https://pncp.gov.br/api"

app = Flask(__name__)
init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/oportunidades")
def api_oportunidades():
    filtros = {}
    if request.args.get("uf"):
        filtros["uf"] = request.args["uf"]
    if request.args.get("modalidade"):
        filtros["modalidade"] = int(request.args["modalidade"])
    if request.args.get("status"):
        filtros["status"] = request.args["status"]
    if request.args.get("favorito"):
        filtros["favorito"] = True
    if request.args.get("portal"):
        filtros["portal"] = request.args["portal"]
    if request.args.get("valor_min"):
        filtros["valor_min"] = float(request.args["valor_min"])
    if request.args.get("valor_max"):
        filtros["valor_max"] = float(request.args["valor_max"])
    if request.args.get("busca"):
        filtros["busca"] = request.args["busca"]
    if request.args.get("data_de"):
        filtros["data_de"] = request.args["data_de"]
    if request.args.get("data_ate"):
        filtros["data_ate"] = request.args["data_ate"]

    ops = listar_oportunidades(filtros)
    return jsonify(ops)


@app.route("/api/estatisticas")
def api_estatisticas():
    return jsonify(estatisticas())


@app.route("/api/oportunidades/<path:id_op>/status", methods=["POST"])
def api_status(id_op):
    data = request.get_json()
    atualizar_status(id_op, data["status"])
    return jsonify({"ok": True})


@app.route("/api/oportunidades/<path:id_op>/favorito", methods=["POST"])
def api_favorito(id_op):
    fav = toggle_favorito(id_op)
    return jsonify({"favorito": fav})


@app.route("/api/oportunidades/<path:id_op>/notas", methods=["POST"])
def api_notas(id_op):
    data = request.get_json()
    salvar_notas(id_op, data["notas"])
    return jsonify({"ok": True})


@app.route("/api/relatorios")
def api_relatorios():
    return jsonify(relatorios())


# ── Acompanhamento ──

def _parse_entrada(entrada):
    """Extrai cnpj, ano, sequencial de link PNCP ou texto separado por /."""
    entrada = entrada.strip()
    # Link: pncp.gov.br/app/editais/CNPJ/ANO/SEQ
    m = re.search(r'(\d{14})/(\d{4})/(\d+)', entrada)
    if m:
        return m.group(1), m.group(2), m.group(3)
    # Formato: CNPJ/ANO/SEQ ou CNPJ ANO SEQ
    partes = re.split(r'[/\s,;-]+', entrada)
    partes = [p.strip() for p in partes if p.strip()]
    if len(partes) >= 3:
        cnpj = partes[0].replace('.', '').replace('/', '').replace('-', '')
        return cnpj, partes[1], partes[2]
    return None, None, None


def _buscar_pncp(cnpj, ano, seq):
    """Busca dados de uma contratação na API do PNCP."""
    url = f"{PNCP_BASE}/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _buscar_itens_pncp(cnpj, ano, seq):
    """Busca itens de uma contratação na API do PNCP."""
    url = f"{PNCP_BASE}/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
    try:
        resp = requests.get(url, timeout=60, params={"pagina": 1, "tamanhoPagina": 50})
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


@app.route("/api/acompanhar", methods=["POST"])
def api_acompanhar():
    data = request.get_json()
    entrada = data.get("entrada", "")
    cnpj, ano, seq = _parse_entrada(entrada)
    if not cnpj:
        return jsonify({"erro": "Formato invalido. Use: CNPJ/ANO/SEQUENCIAL ou cole o link do PNCP"}), 400

    try:
        info = _buscar_pncp(cnpj, ano, seq)
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return jsonify({"erro": "Licitacao nao encontrada no PNCP"}), 404
        return jsonify({"erro": f"Erro na API PNCP: {e.response.status_code}"}), 502
    except Exception as e:
        return jsonify({"erro": f"Erro ao consultar PNCP: {str(e)}"}), 502

    # Buscar itens
    itens = _buscar_itens_pncp(cnpj, ano, seq)

    id_acomp = f"{cnpj}-{ano}-{seq}"
    modalidade_cod = info.get("modalidadeId", info.get("codigoModalidadeContratacao", ""))
    MODALIDADES = {1:"Leilao-Loss",2:"Dialogo Competitivo",3:"Concurso",4:"Concorrencia-Loss",
                   5:"Concorrencia",6:"Pregao Eletronico",7:"Pregao Presencial",
                   8:"Dispensa",9:"Inexigibilidade",10:"Manifestacao de Interesse",
                   11:"Pre-qualificacao",12:"Credenciamento",13:"Leilao"}

    dados = {
        "id": id_acomp,
        "cnpj": cnpj,
        "ano": ano,
        "sequencial": seq,
        "orgao": info.get("orgaoEntidade", {}).get("razaoSocial", ""),
        "unidade": info.get("unidadeOrgao", {}).get("nomeUnidade", ""),
        "uf": info.get("unidadeOrgao", {}).get("ufSigla", ""),
        "modalidade": MODALIDADES.get(modalidade_cod, f"Codigo {modalidade_cod}"),
        "objeto": info.get("objetoCompra", ""),
        "valor_estimado": info.get("valorTotalEstimado"),
        "data_abertura": info.get("dataAberturaProposta"),
        "data_encerramento": info.get("dataEncerramentoProposta"),
        "link": f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}",
        "itens_json": json.dumps(itens if isinstance(itens, list) else itens.get("data", itens), ensure_ascii=False),
    }
    inserir_acompanhamento(dados)
    return jsonify({"ok": True, "id": id_acomp, "dados": dados})


@app.route("/api/acompanhamentos")
def api_acompanhamentos():
    return jsonify(listar_acompanhamentos())


@app.route("/api/acompanhamentos/<path:id_acomp>/detalhes")
def api_detalhes_acompanhamento(id_acomp):
    acomp = buscar_acompanhamento(id_acomp)
    if not acomp:
        return jsonify({"erro": "Nao encontrado"}), 404

    # Buscar itens atualizados da API
    itens = _buscar_itens_pncp(acomp["cnpj"], acomp["ano"], acomp["sequencial"])
    itens_lista = itens if isinstance(itens, list) else itens.get("data", itens)

    # Buscar resultados por item
    for item in (itens_lista if isinstance(itens_lista, list) else []):
        num = item.get("numeroItem", "")
        if num:
            try:
                url = f"{PNCP_BASE}/consulta/v1/orgaos/{acomp['cnpj']}/compras/{acomp['ano']}/{acomp['sequencial']}/itens/{num}/resultados"
                r = requests.get(url, timeout=15)
                if r.ok:
                    item["resultados"] = r.json()
            except Exception:
                pass

    acomp["itens"] = itens_lista
    return jsonify(acomp)


@app.route("/api/acompanhamentos/<path:id_acomp>", methods=["DELETE"])
def api_remover_acompanhamento(id_acomp):
    remover_acompanhamento(id_acomp)
    return jsonify({"ok": True})


@app.route("/api/acompanhamentos/<path:id_acomp>/notas", methods=["POST"])
def api_notas_acompanhamento(id_acomp):
    data = request.get_json()
    salvar_notas_acompanhamento(id_acomp, data["notas"])
    return jsonify({"ok": True})


# ── Comentarios / Chat ──

@app.route("/api/comentarios/<path:ref_id>")
def api_listar_comentarios(ref_id):
    return jsonify(listar_comentarios(ref_id))


@app.route("/api/comentarios/<path:ref_id>", methods=["POST"])
def api_adicionar_comentario(ref_id):
    data = request.get_json()
    texto = data.get("texto", "").strip()
    if not texto:
        return jsonify({"erro": "Texto vazio"}), 400
    adicionar_comentario(
        ref_id, texto,
        tipo=data.get("tipo", "anotacao"),
        autor=data.get("autor", "Eu"),
        nivel=data.get("nivel", "normal")
    )
    return jsonify({"ok": True})


@app.route("/api/comentarios/remover/<int:comentario_id>", methods=["DELETE"])
def api_remover_comentario(comentario_id):
    remover_comentario(comentario_id)
    return jsonify({"ok": True})


@app.route("/api/comentarios/contar/<path:ref_id>")
def api_contar_comentarios(ref_id):
    return jsonify({"count": contar_comentarios(ref_id)})


@app.route("/api/comentarios/contar-batch", methods=["POST"])
def api_contar_batch():
    data = request.get_json()
    ids = data.get("ids", [])
    return jsonify(contar_comentarios_batch(ids))


@app.route("/api/comentarios/nao-lidos", methods=["POST"])
def api_nao_lidos():
    data = request.get_json()
    ref_timestamps = data.get("refs", {})
    return jsonify(contar_nao_lidos_batch(ref_timestamps))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
