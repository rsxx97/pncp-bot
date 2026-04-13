"""Sistema de alertas do dashboard."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from api.deps import get_connection

router = APIRouter(prefix="/api/alertas", tags=["alertas"])


@router.get("/")
def listar_alertas(limit: int = Query(20)):
    """Lista alertas recentes (editais urgentes, mensagens, resultados)."""
    conn = get_connection()
    agora = datetime.now()
    alertas = []

    # 1. Editais com prazo < 48h
    try:
        rows = conn.execute("""
            SELECT pncp_id, orgao_nome, objeto, valor_estimado, data_encerramento
            FROM editais
            WHERE status NOT IN ('arquivado', 'pregao_ext')
            AND data_encerramento IS NOT NULL
            AND fonte != 'extension'
            ORDER BY data_encerramento ASC
        """).fetchall()

        for r in rows:
            try:
                enc = datetime.fromisoformat(r["data_encerramento"].replace("Z", "").split("+")[0])
                diff = enc - agora
                horas = diff.total_seconds() / 3600

                if 0 < horas < 48:
                    alertas.append({
                        "tipo": "prazo_urgente",
                        "nivel": "critico" if horas < 24 else "atencao",
                        "titulo": f"Prazo urgente: {r['orgao_nome'][:30]}",
                        "descricao": f"{r['objeto'][:80]} — {int(horas)}h restantes",
                        "pncp_id": r["pncp_id"],
                        "horas_restantes": round(horas, 1),
                        "timestamp": agora.isoformat(),
                    })
                elif -24 < horas <= 0:
                    alertas.append({
                        "tipo": "prazo_encerrado",
                        "nivel": "info",
                        "titulo": f"Encerrado: {r['orgao_nome'][:30]}",
                        "descricao": f"{r['objeto'][:80]} — encerrou há {abs(int(horas))}h",
                        "pncp_id": r["pncp_id"],
                        "timestamp": agora.isoformat(),
                    })
            except:
                continue
    except:
        pass

    # 2. Pregões com novidades
    try:
        rows = conn.execute("""
            SELECT p.id, p.pncp_id, p.status, p.vencedor_nome, p.updated_at,
                   e.orgao_nome, e.objeto
            FROM pregoes p
            LEFT JOIN editais e ON p.pncp_id = e.pncp_id
            ORDER BY p.updated_at DESC LIMIT 10
        """).fetchall()

        for r in rows:
            if r["status"] == "resultado" and r["vencedor_nome"]:
                alertas.append({
                    "tipo": "resultado_pregao",
                    "nivel": "sucesso" if "MANUTEC" in (r["vencedor_nome"] or "").upper() or "MIAMI" in (r["vencedor_nome"] or "").upper() else "info",
                    "titulo": f"Resultado: {(r['orgao_nome'] or 'Pregão')[:30]}",
                    "descricao": f"Vencedor: {r['vencedor_nome'][:40]}",
                    "pregao_id": r["id"],
                    "timestamp": r["updated_at"] or agora.isoformat(),
                })
    except:
        pass

    # 3. Mensagens recentes do pregoeiro
    try:
        rows = conn.execute("""
            SELECT cp.mensagem, cp.remetente, cp.horario, cp.pregao_id,
                   p.pncp_id, e.orgao_nome
            FROM chat_pregao cp
            JOIN pregoes p ON cp.pregao_id = p.id
            LEFT JOIN editais e ON p.pncp_id = e.pncp_id
            WHERE cp.remetente = 'pregoeiro'
            ORDER BY cp.id DESC LIMIT 5
        """).fetchall()

        for r in rows:
            alertas.append({
                "tipo": "mensagem_pregoeiro",
                "nivel": "atencao",
                "titulo": f"Pregoeiro: {(r['orgao_nome'] or 'Pregão')[:30]}",
                "descricao": (r["mensagem"] or "")[:100],
                "pregao_id": r["pregao_id"],
                "timestamp": r["horario"] or agora.isoformat(),
            })
    except:
        pass

    # Ordena por timestamp (mais recentes primeiro)
    alertas.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {"alertas": alertas[:limit], "total": len(alertas)}


@router.get("/contagem")
def contagem_alertas():
    """Retorna contagem de alertas por nível (para badge)."""
    conn = get_connection()
    agora = datetime.now()
    criticos = 0
    atencao = 0

    try:
        rows = conn.execute("""
            SELECT data_encerramento FROM editais
            WHERE status NOT IN ('arquivado', 'pregao_ext')
            AND data_encerramento IS NOT NULL AND fonte != 'extension'
        """).fetchall()

        for r in rows:
            try:
                enc = datetime.fromisoformat(r["data_encerramento"].replace("Z", "").split("+")[0])
                horas = (enc - agora).total_seconds() / 3600
                if 0 < horas < 24:
                    criticos += 1
                elif 24 <= horas < 48:
                    atencao += 1
            except:
                continue
    except:
        pass

    return {"criticos": criticos, "atencao": atencao, "total": criticos + atencao}
