"""Inicia servidor + monitor PNCP + bot Telegram em threads."""
import os
import sys
import time
import logging
import threading

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("start")


def iniciar_monitor():
    """Roda monitor PNCP periodicamente."""
    from shared.database import init_db
    init_db()

    intervalo = int(os.environ.get("MONITOR_INTERVALO_MIN", 30)) * 60
    log.info(f"Monitor PNCP iniciado (intervalo: {intervalo // 60} min)")

    while True:
        try:
            from agente1_monitor.main import executar_monitor
            result = executar_monitor(usar_llm=False, incluir_nacional=False)
            stats = result.get("stats", {})
            log.info(f"Monitor: {stats.get('novos', 0)} novos, {stats.get('relevantes', 0)} relevantes")
        except Exception as e:
            log.error(f"Erro no monitor: {e}")

        time.sleep(intervalo)


def iniciar_bot():
    """Inicia bot Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        log.warning("TELEGRAM_BOT_TOKEN não configurado. Bot desativado.")
        return

    try:
        from bot_telegram.main import iniciar_bot as _iniciar_bot
        log.info("Bot Telegram iniciado")
        _iniciar_bot()
    except Exception as e:
        log.error(f"Erro no bot: {e}")


def iniciar_servidor():
    """Inicia FastAPI com uvicorn."""
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    log.info(f"Servidor iniciando na porta {port}")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    from shared.database import init_db
    init_db()
    log.info("Banco inicializado")

    # Monitor em thread
    monitor_thread = threading.Thread(target=iniciar_monitor, daemon=True)
    monitor_thread.start()

    # Bot em thread
    bot_thread = threading.Thread(target=iniciar_bot, daemon=True)
    bot_thread.start()

    # Servidor no main thread (blocking)
    iniciar_servidor()
