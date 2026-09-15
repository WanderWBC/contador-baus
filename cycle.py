from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CYCLE_TZ = ZoneInfo("America/Sao_Paulo")
CYCLE_START_HOUR = 14  # 14h de Brasília, todo domingo


def cycle_start_for(dt_utc):
    """Dado um datetime UTC, devolve o datetime UTC do domingo 14h de Brasília
    mais recente que seja <= dt_utc (ou seja, o início do ciclo em que dt_utc cai)."""
    local = dt_utc.astimezone(CYCLE_TZ)
    # weekday(): Monday=0 ... Sunday=6. Dias desde o último domingo:
    days_since_sunday = (local.weekday() + 1) % 7
    candidate_date = local.date() - timedelta(days=days_since_sunday)
    candidate = datetime(
        candidate_date.year, candidate_date.month, candidate_date.day,
        CYCLE_START_HOUR, 0, 0, tzinfo=CYCLE_TZ,
    )
    if candidate > local:
        candidate -= timedelta(days=7)
    return candidate.astimezone(timezone.utc)


def current_cycle_start(now_utc=None):
    """ISO string (UTC) do início do ciclo atual."""
    now_utc = now_utc or datetime.now(timezone.utc)
    return cycle_start_for(now_utc).isoformat()


def previous_cycle_bounds(now_utc=None):
    """(inicio, fim) ISO em UTC do ciclo anterior ao atual (já fechado)."""
    now_utc = now_utc or datetime.now(timezone.utc)
    current_start = cycle_start_for(now_utc)
    previous_start = current_start - timedelta(days=7)
    return previous_start.isoformat(), current_start.isoformat()
