"""Métricas Prometheus do Radar."""
from prometheus_client import Counter, Gauge, Histogram

RADAR_EVENTOS_TOTAL = Counter(
    "radar_eventos_total",
    "Total de eventos detectados",
    ["portal", "tipo", "criticidade"],
)

RADAR_FETCH_TOTAL = Counter(
    "radar_fetch_total",
    "Total de fetches a portais",
    ["portal", "status"],   # status: ok, erro, rate_limit, not_found, auth_error
)

RADAR_FETCH_DURACAO = Histogram(
    "radar_fetch_duracao_seg",
    "Duração de fetches a portais",
    ["portal"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60),
)

RADAR_NOTIF_TOTAL = Counter(
    "radar_notif_total",
    "Total de notificações enviadas",
    ["canal", "status"],
)

RADAR_PREGOES_ATIVOS = Gauge(
    "radar_pregoes_ativos",
    "Quantidade de pregões sendo monitorados ativamente",
    ["portal"],
)

RADAR_SSE_CONEXOES = Gauge(
    "radar_sse_conexoes",
    "Conexões SSE ativas por tenant",
)
