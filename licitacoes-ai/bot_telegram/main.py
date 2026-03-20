"""Bot Telegram principal — polling loop com python-telegram-bot."""
import json
import logging
import asyncio
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from shared.database import init_db

log = logging.getLogger("bot_telegram")

# Lazy imports para evitar circular
_telegram_available = False
try:
    from telegram import Update, Bot
    from telegram.ext import (
        Application, CommandHandler, CallbackQueryHandler,
        MessageHandler, filters,
    )
    _telegram_available = True
except ImportError:
    log.warning("python-telegram-bot não instalado. Instale com: pip install python-telegram-bot")


async def cmd_start(update, context):
    from bot_telegram.handlers import handle_start
    msg, keyboard = handle_start()
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_status(update, context):
    from bot_telegram.handlers import handle_status
    msg, keyboard = handle_status()
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_ver(update, context):
    from bot_telegram.handlers import handle_ver_edital
    if not context.args:
        await update.message.reply_text("Use: /ver <pncp_id>")
        return
    pncp_id = context.args[0]
    msg, keyboard = handle_ver_edital(pncp_id)
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_buscar(update, context):
    from bot_telegram.handlers import handle_buscar
    if not context.args:
        await update.message.reply_text("Use: /buscar <termo>")
        return
    termo = " ".join(context.args)
    msg, keyboard = handle_buscar(termo)
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_oportunidades(update, context):
    from bot_telegram.handlers import handle_oportunidades
    status = context.args[0] if context.args else "novo"
    msg, keyboard = handle_oportunidades(status)
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_monitor(update, context):
    """Executa o monitor manualmente."""
    await update.message.reply_text("🔄 Executando monitor...")

    import threading

    def _run():
        try:
            from agente1_monitor.main import executar_monitor
            stats = executar_monitor()

            # Envia resultado
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text(
                    f"✅ Monitor concluído!\n\n"
                    f"📋 Novos: {stats.get('novos_relevantes', 0)}\n"
                    f"📊 Total processados: {stats.get('total_processados', 0)}"
                ),
                asyncio.get_event_loop(),
            )
        except Exception as e:
            log.error(f"Erro no monitor: {e}")

    threading.Thread(target=_run, daemon=True).start()


async def cmd_pipeline(update, context):
    """Executa pipeline completo para um edital."""
    if not context.args:
        await update.message.reply_text("Use: /pipeline <pncp_id>")
        return

    pncp_id = context.args[0]
    await update.message.reply_text(f"🚀 Pipeline iniciado para `{pncp_id}`...", parse_mode="Markdown")

    import threading

    def _run():
        try:
            from agente2_analista.main import analisar_edital
            from agente3_precificador.main import precificar_edital
            from agente4_competitivo.main import analisar_edital_competitivo

            log.info(f"Pipeline: analisando {pncp_id}")
            analisar_edital(pncp_id)

            log.info(f"Pipeline: precificando {pncp_id}")
            precificar_edital(pncp_id)

            log.info(f"Pipeline: competitivo {pncp_id}")
            analisar_edital_competitivo(pncp_id)

            log.info(f"Pipeline concluído: {pncp_id}")
        except Exception as e:
            log.error(f"Erro no pipeline de {pncp_id}: {e}")

    threading.Thread(target=_run, daemon=True).start()


async def cmd_planilha(update, context):
    """Envia planilha .xlsx de um edital."""
    if not context.args:
        await update.message.reply_text("Use: /planilha <pncp_id>")
        return

    pncp_id = context.args[0]
    from shared.database import get_edital
    edital = get_edital(pncp_id)

    if not edital or not edital.get("planilha_path"):
        await update.message.reply_text("❌ Planilha não encontrada.")
        return

    path = Path(edital["planilha_path"])
    if not path.exists():
        await update.message.reply_text("❌ Arquivo da planilha não existe no servidor.")
        return

    await update.message.reply_document(
        document=open(path, "rb"),
        filename=path.name,
        caption=f"📄 Planilha de custos: {pncp_id}",
    )


async def callback_handler(update, context):
    """Handler genérico para callbacks de botões inline."""
    query = update.callback_query
    await query.answer()

    from bot_telegram.callbacks import processar_callback
    msg, keyboard = processar_callback(query.data)

    try:
        await query.edit_message_text(
            text=msg,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    except Exception:
        # Se falhar ao editar (mesma mensagem), envia nova
        await query.message.reply_text(
            text=msg,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


def criar_app() -> "Application":
    """Cria e configura a Application do telegram bot."""
    if not _telegram_available:
        raise ImportError("python-telegram-bot não instalado")
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado no .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ver", cmd_ver))
    app.add_handler(CommandHandler("buscar", cmd_buscar))
    app.add_handler(CommandHandler("oportunidades", cmd_oportunidades))
    app.add_handler(CommandHandler("monitor", cmd_monitor))
    app.add_handler(CommandHandler("pipeline", cmd_pipeline))
    app.add_handler(CommandHandler("planilha", cmd_planilha))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))

    return app


def iniciar_bot():
    """Inicia o bot em polling mode."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    init_db()
    log.info("Bot Telegram iniciando...")

    app = criar_app()
    log.info("Bot pronto. Aguardando mensagens...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    iniciar_bot()
