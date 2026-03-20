"""Entry point principal — inicia dashboard + bot + scheduler."""
import argparse
import logging
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import TELEGRAM_BOT_TOKEN
from shared.database import init_db


def iniciar_dashboard(host: str = "0.0.0.0", port: int = 8000):
    """Inicia o dashboard FastAPI."""
    import uvicorn
    from dashboard.api import app
    uvicorn.run(app, host=host, port=port, log_level="info")


def iniciar_bot():
    """Inicia o bot Telegram."""
    from bot_telegram.main import iniciar_bot as _iniciar_bot
    _iniciar_bot()


def iniciar_scheduler():
    """Inicia o scheduler do monitor."""
    from agente1_monitor.scheduler import iniciar_scheduler as _iniciar
    _iniciar()


def main():
    parser = argparse.ArgumentParser(description="Licitacoes AI — Sistema Multi-Agente")
    parser.add_argument("comando", choices=["dashboard", "bot", "monitor", "pipeline", "tudo"],
                        help="O que iniciar")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--pncp-id", help="PNCP ID para pipeline individual")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    log = logging.getLogger("main")

    init_db()
    log.info("Banco de dados inicializado.")

    if args.comando == "dashboard":
        log.info(f"Iniciando dashboard em http://{args.host}:{args.port}")
        iniciar_dashboard(args.host, args.port)

    elif args.comando == "bot":
        if not TELEGRAM_BOT_TOKEN:
            log.error("TELEGRAM_BOT_TOKEN nao configurado no .env")
            sys.exit(1)
        log.info("Iniciando bot Telegram...")
        iniciar_bot()

    elif args.comando == "monitor":
        log.info("Executando monitor uma vez...")
        from agente1_monitor.main import executar_monitor
        stats = executar_monitor()
        log.info(f"Monitor concluido: {stats}")

    elif args.comando == "pipeline":
        if not args.pncp_id:
            log.error("Use --pncp-id para especificar o edital")
            sys.exit(1)
        log.info(f"Executando pipeline para {args.pncp_id}...")
        from agente2_analista.main import analisar_edital
        from agente3_precificador.main import precificar_edital
        from agente4_competitivo.main import analisar_edital_competitivo

        analisar_edital(args.pncp_id)
        precificar_edital(args.pncp_id)
        analisar_edital_competitivo(args.pncp_id)
        log.info("Pipeline concluido!")

    elif args.comando == "tudo":
        log.info("Iniciando sistema completo...")

        # Scheduler em thread
        threading.Thread(target=iniciar_scheduler, daemon=True).start()
        log.info("Scheduler iniciado.")

        # Bot em thread (se token configurado)
        if TELEGRAM_BOT_TOKEN:
            threading.Thread(target=iniciar_bot, daemon=True).start()
            log.info("Bot Telegram iniciado.")
        else:
            log.warning("TELEGRAM_BOT_TOKEN nao configurado. Bot desativado.")

        # Dashboard no main thread (blocking)
        log.info(f"Dashboard em http://{args.host}:{args.port}")
        iniciar_dashboard(args.host, args.port)


if __name__ == "__main__":
    main()
