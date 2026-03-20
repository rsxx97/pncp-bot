"""Handlers de comandos do bot Telegram."""
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import (
    contar_editais_por_status, get_editais_pendentes, get_editais_recentes,
    get_custo_total, get_monitor_state, get_edital,
)
from shared.utils import formatar_valor
from bot_telegram.keyboards import (
    teclado_principal, teclado_oportunidades, teclado_relatorios, teclado_config,
    teclado_edital,
)

log = logging.getLogger("bot_handlers")


def handle_start() -> tuple[str, dict]:
    """Comando /start — menu principal."""
    msg = (
        "🤖 *Bot Licitações AI*\n\n"
        "Sistema inteligente de monitoramento, análise e precificação "
        "de licitações públicas.\n\n"
        "Selecione uma opção:"
    )
    return msg, teclado_principal()


def handle_status() -> tuple[str, dict | None]:
    """Comando /status — resumo geral."""
    contagem = contar_editais_por_status()
    monitor = get_monitor_state()
    custo_30d = get_custo_total(30)

    total = sum(contagem.values())
    status_monitor = "🟢 Ativo" if monitor.get("ativo") else "🔴 Parado"
    ultima = monitor.get("ultima_consulta", "Nunca")

    msg = (
        "📊 *Status do Sistema*\n\n"
        f"Monitor: {status_monitor}\n"
        f"Última consulta: {ultima}\n\n"
        f"📋 *Editais ({total} total)*\n"
    )

    status_emoji = {
        "novo": "🆕",
        "classificado": "📝",
        "analisado": "🔍",
        "precificado": "💰",
        "competitivo_pronto": "🎯",
        "enviado": "📤",
        "favorito": "⭐",
        "descartado": "🗑️",
        "nogo": "❌",
        "erro_analise": "⚠️",
        "erro_precificacao": "⚠️",
    }

    for status, count in sorted(contagem.items()):
        emoji = status_emoji.get(status, "•")
        msg += f"  {emoji} {status}: {count}\n"

    msg += f"\n💵 Custo API (30 dias): ${custo_30d:.2f}"

    return msg, None


def handle_oportunidades(status_filtro: str = "novo", limit: int = 10) -> tuple[str, dict]:
    """Lista oportunidades por status."""
    editais = get_editais_pendentes(status=status_filtro, limit=limit)

    status_labels = {
        "novo": "🆕 Novos",
        "classificado": "📝 Classificados",
        "analisado": "✅ Analisados (Go)",
        "precificado": "💰 Precificados",
        "competitivo_pronto": "🎯 Prontos para Lance",
        "favorito": "⭐ Favoritos",
        "nogo": "❌ No-Go",
    }

    label = status_labels.get(status_filtro, status_filtro)
    msg = f"*{label}* ({len(editais)} resultados)\n\n"

    if not editais:
        msg += "Nenhum edital encontrado neste status."
        return msg, teclado_oportunidades()

    for i, e in enumerate(editais[:10], 1):
        valor = formatar_valor(e.get("valor_estimado"))
        score = e.get("score_relevancia", "?")
        objeto = (e.get("objeto") or "")[:80]
        uf = e.get("uf", "?")
        pncp_id = e.get("pncp_id", "")

        msg += (
            f"*{i}.* [{score}] {objeto}...\n"
            f"   💰 {valor} | 📍 {uf}\n"
            f"   `/ver {pncp_id}`\n\n"
        )

    return msg, teclado_oportunidades()


def handle_ver_edital(pncp_id: str) -> tuple[str, dict]:
    """Detalhe de um edital."""
    edital = get_edital(pncp_id)
    if not edital:
        return f"❌ Edital `{pncp_id}` não encontrado.", teclado_oportunidades()

    valor = formatar_valor(edital.get("valor_estimado"))
    score = edital.get("score_relevancia", "?")
    status = edital.get("status", "?")
    empresa = edital.get("empresa_sugerida", "-")
    parecer = edital.get("parecer", "-")

    msg = (
        f"📋 *Edital: {pncp_id}*\n\n"
        f"🏢 {edital.get('orgao_nome', '?')}\n"
        f"📝 {edital.get('objeto', '?')}\n\n"
        f"💰 Valor: {valor}\n"
        f"📍 {edital.get('uf', '?')} — {edital.get('municipio', '?')}\n"
        f"📅 Abertura: {edital.get('data_abertura', '?')}\n"
        f"📅 Encerramento: {edital.get('data_encerramento', '?')}\n\n"
        f"📊 Score: {score}/100\n"
        f"📌 Status: {status}\n"
        f"🏭 Empresa: {empresa}\n"
        f"📋 Parecer: {parecer}\n"
    )

    if edital.get("valor_proposta"):
        msg += f"\n💵 Proposta: {formatar_valor(edital['valor_proposta'])}"
        msg += f"\n📈 Margem: {edital.get('margem_percentual', 0):.1f}%"
        msg += f"\n📊 BDI: {edital.get('bdi_percentual', 0):.2f}%"

    if edital.get("lance_sugerido_min"):
        msg += f"\n\n🎯 Lance sugerido:"
        msg += f"\n   Min: {formatar_valor(edital['lance_sugerido_min'])}"
        msg += f"\n   Max: {formatar_valor(edital['lance_sugerido_max'])}"

    if edital.get("link_edital"):
        msg += f"\n\n🔗 {edital['link_edital']}"

    return msg, teclado_edital(pncp_id, status)


def handle_relatorio_resumo() -> tuple[str, dict | None]:
    """Relatório resumo."""
    contagem = contar_editais_por_status()
    custo = get_custo_total(30)

    total = sum(contagem.values())
    go = contagem.get("analisado", 0) + contagem.get("precificado", 0) + contagem.get("competitivo_pronto", 0)
    nogo = contagem.get("nogo", 0) + contagem.get("descartado", 0)

    taxa_aprovacao = (go / (go + nogo) * 100) if (go + nogo) > 0 else 0

    msg = (
        "📈 *Relatório Resumo*\n\n"
        f"📋 Total editais: {total}\n"
        f"✅ Aprovados (Go): {go}\n"
        f"❌ Rejeitados: {nogo}\n"
        f"📊 Taxa aprovação: {taxa_aprovacao:.1f}%\n\n"
        f"💰 Precificados: {contagem.get('precificado', 0)}\n"
        f"🎯 Prontos p/ lance: {contagem.get('competitivo_pronto', 0)}\n\n"
        f"💵 Custo API (30d): ${custo:.2f}\n"
    )

    return msg, teclado_relatorios()


def handle_buscar(termo: str) -> tuple[str, dict | None]:
    """Busca editais por termo no objeto."""
    from shared.database import get_db

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM editais WHERE objeto LIKE ? ORDER BY created_at DESC LIMIT 10",
        (f"%{termo}%",),
    ).fetchall()

    if not rows:
        return f"🔍 Nenhum resultado para '{termo}'.", teclado_principal()

    msg = f"🔍 *Busca: '{termo}'* ({len(rows)} resultados)\n\n"
    for i, r in enumerate(rows, 1):
        e = dict(r)
        valor = formatar_valor(e.get("valor_estimado"))
        objeto = (e.get("objeto") or "")[:80]
        msg += f"*{i}.* {objeto}...\n   💰 {valor} | `/ver {e['pncp_id']}`\n\n"

    return msg, None
