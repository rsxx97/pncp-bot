"""Scheduler para monitoramento periódico usando APScheduler."""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import INTERVALO_MONITOR_MINUTOS

log = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None


def _job_monitor():
    """Job executado periodicamente pelo scheduler."""
    from agente1_monitor.main import executar_monitor
    try:
        log.info("Scheduler: iniciando ciclo de monitoramento...")
        result = executar_monitor(usar_llm=False, dias_retroativos=3)
        stats = result["stats"]
        log.info(
            f"Scheduler: ciclo concluído. "
            f"{stats['relevantes']} relevantes de {stats['novos']} novos"
        )

        # Se houver relevantes, poderia notificar Telegram aqui
        # (será integrado na Fase 6 - Bot)
        return result

    except Exception as e:
        log.exception(f"Scheduler: erro no ciclo: {e}")


def setup_scheduler(intervalo_minutos: int = None) -> BackgroundScheduler:
    """Configura e retorna o scheduler (não inicia ainda)."""
    global _scheduler

    if intervalo_minutos is None:
        intervalo_minutos = INTERVALO_MONITOR_MINUTOS

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _job_monitor,
        trigger=IntervalTrigger(minutes=intervalo_minutos),
        id="monitor_pncp",
        name=f"Monitor PNCP (a cada {intervalo_minutos} min)",
        replace_existing=True,
        max_instances=1,  # Evita execuções simultâneas
    )

    log.info(f"Scheduler configurado: monitor a cada {intervalo_minutos} minutos")
    return _scheduler


def start_scheduler():
    """Inicia o scheduler."""
    global _scheduler
    if _scheduler is None:
        setup_scheduler()
    if not _scheduler.running:
        _scheduler.start()
        log.info("Scheduler iniciado")


def stop_scheduler():
    """Para o scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler parado")


def trigger_now():
    """Executa o monitor imediatamente (fora do schedule)."""
    return _job_monitor()
