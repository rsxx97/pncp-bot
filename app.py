from flask import Flask, render_template, request, jsonify
from database import init_db, listar_oportunidades, atualizar_status, toggle_favorito, salvar_notas, estatisticas

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
