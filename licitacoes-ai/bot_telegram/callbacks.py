"""Handlers de callback (botões inline) do bot Telegram."""
import logging
import threading
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import (
    atualizar_status_edital, get_edital, get_monitor_state, set_monitor_state,
    init_db,
)
from shared.utils import formatar_valor
from bot_telegram.handlers import (
    handle_start, handle_oportunidades, handle_ver_edital,
    handle_relatorio_resumo, handle_status,
)
from bot_telegram.keyboards import (
    teclado_principal, teclado_oportunidades, teclado_relatorios,
    teclado_config, teclado_edital,
)

log = logging.getLogger("bot_callbacks")


def processar_callback(callback_data: str) -> tuple[str, dict | None]:
    """Processa callback_data e retorna (mensagem, teclado).

    Returns:
        Tuple (texto_resposta, reply_markup ou None).
    """
    # Menus principais
    if callback_data == "menu_principal":
        return handle_start()

    if callback_data == "menu_oportunidades":
        return handle_oportunidades("novo")

    if callback_data == "menu_relatorios":
        return handle_relatorio_resumo()

    if callback_data == "menu_buscar":
        return "🔍 Use o comando:\n`/buscar <termo>`", teclado_principal()

    if callback_data == "menu_config":
        return _handle_config_menu()

    # Filtros de oportunidades
    filtros = {
        "oport_novos": "novo",
        "oport_go": "analisado",
        "oport_precificados": "precificado",
        "oport_prontos": "competitivo_pronto",
        "oport_favoritos": "favorito",
        "oport_nogo": "nogo",
    }
    if callback_data in filtros:
        return handle_oportunidades(filtros[callback_data])

    # Relatórios
    if callback_data == "rel_resumo":
        return handle_relatorio_resumo()

    if callback_data == "rel_custos":
        return _handle_custos()

    if callback_data == "rel_status":
        return handle_status()

    if callback_data == "rel_top":
        return _handle_top_oportunidades()

    # Ações em editais
    if callback_data.startswith("analisar_"):
        pncp_id = callback_data[len("analisar_"):]
        return _executar_analise_async(pncp_id)

    if callback_data.startswith("precificar_"):
        pncp_id = callback_data[len("precificar_"):]
        return _executar_precificacao_async(pncp_id)

    if callback_data.startswith("competitivo_"):
        pncp_id = callback_data[len("competitivo_"):]
        return _executar_competitivo_async(pncp_id)

    if callback_data.startswith("favoritar_"):
        pncp_id = callback_data[len("favoritar_"):]
        return _favoritar(pncp_id)

    if callback_data.startswith("descartar_"):
        pncp_id = callback_data[len("descartar_"):]
        return _descartar(pncp_id)

    if callback_data.startswith("planilha_"):
        pncp_id = callback_data[len("planilha_"):]
        return _enviar_planilha(pncp_id)

    # Config
    if callback_data == "cfg_monitor_status":
        return _monitor_status()

    if callback_data == "cfg_monitor_toggle":
        return _monitor_toggle()

    if callback_data == "cfg_importar_ccts":
        return _importar_ccts()

    if callback_data == "cfg_concorrentes":
        return _listar_concorrentes()

    if callback_data == "executar_monitor":
        return _executar_monitor_async()

    return f"❓ Ação desconhecida: {callback_data}", teclado_principal()


# ── Ações assíncronas (executam em thread) ──────────────────────────

def _executar_analise_async(pncp_id: str) -> tuple[str, dict | None]:
    """Inicia análise de edital em background."""
    edital = get_edital(pncp_id)
    if not edital:
        return f"❌ Edital {pncp_id} não encontrado.", None

    def _run():
        try:
            from agente2_analista.main import analisar_edital
            analisar_edital(pncp_id)
            log.info(f"Análise concluída: {pncp_id}")
        except Exception as e:
            log.error(f"Erro na análise de {pncp_id}: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return f"🔍 Análise iniciada para `{pncp_id}`.\nVocê será notificado quando concluir.", teclado_oportunidades()


def _executar_precificacao_async(pncp_id: str) -> tuple[str, dict | None]:
    """Inicia precificação em background."""
    def _run():
        try:
            from agente3_precificador.main import precificar_edital
            precificar_edital(pncp_id)
            log.info(f"Precificação concluída: {pncp_id}")
        except Exception as e:
            log.error(f"Erro na precificação de {pncp_id}: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return f"💰 Precificação iniciada para `{pncp_id}`.", teclado_oportunidades()


def _executar_competitivo_async(pncp_id: str) -> tuple[str, dict | None]:
    """Inicia análise competitiva em background."""
    def _run():
        try:
            from agente4_competitivo.main import analisar_edital_competitivo
            analisar_edital_competitivo(pncp_id)
            log.info(f"Análise competitiva concluída: {pncp_id}")
        except Exception as e:
            log.error(f"Erro na análise competitiva de {pncp_id}: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return f"🎯 Análise competitiva iniciada para `{pncp_id}`.", teclado_oportunidades()


def _executar_monitor_async() -> tuple[str, dict | None]:
    """Executa monitor manualmente."""
    def _run():
        try:
            from agente1_monitor.main import executar_monitor
            stats = executar_monitor()
            log.info(f"Monitor executado: {stats}")
        except Exception as e:
            log.error(f"Erro no monitor: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return "🔄 Monitor iniciado. Aguarde a conclusão...", teclado_principal()


# ── Ações diretas ────────────────────────────────────────────────

def _favoritar(pncp_id: str) -> tuple[str, dict | None]:
    atualizar_status_edital(pncp_id, "favorito")
    return f"⭐ Edital `{pncp_id}` favoritado!", teclado_oportunidades()


def _descartar(pncp_id: str) -> tuple[str, dict | None]:
    atualizar_status_edital(pncp_id, "descartado")
    return f"🗑️ Edital `{pncp_id}` descartado.", teclado_oportunidades()


def _enviar_planilha(pncp_id: str) -> tuple[str, dict | None]:
    edital = get_edital(pncp_id)
    if not edital or not edital.get("planilha_path"):
        return "❌ Planilha não encontrada para este edital.", None

    path = edital["planilha_path"]
    return f"📄 Planilha: `{path}`\n\n(Use /planilha {pncp_id} para receber o arquivo)", teclado_edital(pncp_id, "precificado")


# ── Config ───────────────────────────────────────────────────────

def _handle_config_menu() -> tuple[str, dict]:
    monitor = get_monitor_state()
    status = "🟢 Ativo" if monitor.get("ativo") else "🔴 Parado"
    return f"⚙️ *Configurações*\n\nMonitor: {status}", teclado_config()


def _monitor_status() -> tuple[str, dict]:
    monitor = get_monitor_state()
    status = "🟢 Ativo" if monitor.get("ativo") else "🔴 Parado"
    ultima = monitor.get("ultima_consulta", "Nunca")
    total = monitor.get("total_editais_processados", 0)

    msg = (
        f"🔄 *Status do Monitor*\n\n"
        f"Estado: {status}\n"
        f"Última consulta: {ultima}\n"
        f"Total processados: {total}\n"
    )
    return msg, teclado_config()


def _monitor_toggle() -> tuple[str, dict]:
    monitor = get_monitor_state()
    novo_estado = not monitor.get("ativo", False)
    set_monitor_state(ativo=novo_estado)
    emoji = "▶️" if novo_estado else "⏸️"
    estado = "ativado" if novo_estado else "desativado"
    return f"{emoji} Monitor {estado}!", teclado_config()


def _importar_ccts() -> tuple[str, dict]:
    try:
        from agente3_precificador.cct_manager import importar_ccts_diretorio
        count = importar_ccts_diretorio()
        return f"📦 {count} CCTs importadas com sucesso!", teclado_config()
    except Exception as e:
        return f"❌ Erro ao importar CCTs: {e}", teclado_config()


def _listar_concorrentes() -> tuple[str, dict]:
    from shared.database import listar_concorrentes
    concorrentes = listar_concorrentes()

    if not concorrentes:
        return "👥 Nenhum concorrente cadastrado.", teclado_config()

    msg = "👥 *Concorrentes Cadastrados*\n\n"
    for c in concorrentes:
        nome = c.get("nome_fantasia") or c.get("razao_social") or c.get("cnpj")
        segs = c.get("segmentos", [])
        if isinstance(segs, list):
            segs = ", ".join(segs)
        msg += f"• {nome} — {segs}\n"

    return msg, teclado_config()


def _handle_custos() -> tuple[str, dict]:
    from shared.database import get_custo_total
    custo_7d = get_custo_total(7)
    custo_30d = get_custo_total(30)

    msg = (
        "💵 *Custos API Claude*\n\n"
        f"Últimos 7 dias: ${custo_7d:.4f}\n"
        f"Últimos 30 dias: ${custo_30d:.4f}\n"
    )
    return msg, teclado_relatorios()


def _handle_top_oportunidades() -> tuple[str, dict]:
    from shared.database import get_db

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM editais WHERE score_relevancia IS NOT NULL "
        "ORDER BY score_relevancia DESC LIMIT 10"
    ).fetchall()

    if not rows:
        return "🏆 Nenhuma oportunidade classificada.", teclado_relatorios()

    msg = "🏆 *Top 10 Oportunidades*\n\n"
    for i, r in enumerate(rows, 1):
        e = dict(r)
        score = e.get("score_relevancia", 0)
        valor = formatar_valor(e.get("valor_estimado"))
        objeto = (e.get("objeto") or "")[:60]
        msg += f"*{i}.* [{score}] {objeto}...\n   💰 {valor}\n\n"

    return msg, teclado_relatorios()
