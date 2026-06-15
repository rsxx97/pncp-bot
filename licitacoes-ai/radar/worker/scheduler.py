"""Agenda o tick periódico do worker. APScheduler asyncio em background."""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from radar.worker.monitor import atualizar_gauge_pregoes_ativos, tick_uma_vez

log = logging.getLogger("radar.scheduler")

_scheduler: AsyncIOScheduler | None = None


def iniciar(intervalo_seg: int = 10) -> AsyncIOScheduler:
    """Inicia scheduler. Chame 1x no startup do FastAPI."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_tick_safe, "interval", seconds=intervalo_seg, id="radar_tick", max_instances=1, coalesce=True)
    _scheduler.add_job(atualizar_gauge_pregoes_ativos, "interval", seconds=60, id="radar_gauge")
    _scheduler.start()
    log.info(f"Radar scheduler iniciado (tick a cada {intervalo_seg}s)")
    return _scheduler


async def _tick_safe():
    try:
        await tick_uma_vez()
    except Exception as e:
        log.exception(f"erro no tick: {e}")
