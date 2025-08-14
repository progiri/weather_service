from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple

from django.db.models.functions import TruncDate

from weathers.models import (
    MeteoPointProvider,
    ProviderToken,
    ProviderTokenStat,
)

log = logging.getLogger(__name__)

ISO_DUR_RE = re.compile(
    r"^P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$"
)


def parse_iso_duration(s: str | None) -> Optional[timedelta]:
    if not s:
        return None
    m = ISO_DUR_RE.match(s)
    if not m:
        return None
    d = int(m.group("d") or 0)
    h = int(m.group("h") or 0)
    mi = int(m.group("m") or 0)
    se = int(m.group("s") or 0)
    return timedelta(days=d, hours=h, minutes=mi, seconds=se)


def parse_iso_utc(v: object) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def window_count(win: Dict[str, Any], now: datetime, seconds: int) -> int:
    if not win:
        return 0
    start = parse_iso_utc(win.get("start"))
    if not start:
        return 0
    if (now - start).total_seconds() >= seconds:
        return 0
    return int(win.get("count", 0))


def token_has_capacity(token: ProviderToken, now: datetime) -> Tuple[bool, Dict[str, Any]]:
    limits = (token.provider.config or {}).get("limits") or {}
    if not limits:
        return True, {"reason": "no_limits"}
    stat: ProviderTokenStat | None = token.stats.order_by("-updated_at").first()
    if not stat or not stat.meta:
        return True, {"reason": "no_stats"}

    usage = stat.meta.get("usage") or {}
    day_key = now.strftime("%Y-%m-%d")
    month_key = now.strftime("%Y-%m")

    per_minute = window_count(usage.get("per_minute") or {}, now, 60)
    per_hour = window_count(usage.get("per_hour") or {}, now, 3600)
    by_day = (usage.get("by_day") or {}).get(day_key, 0)
    by_month = (usage.get("by_month") or {}).get(month_key, 0)

    checks = []
    if "per_minute" in limits:
        checks.append(per_minute < int(limits["per_minute"]))
    if "per_hour" in limits:
        checks.append(per_hour < int(limits["per_hour"]))
    if "per_day" in limits:
        checks.append(by_day < int(limits["per_day"]))
    if "per_month" in limits:
        checks.append(by_month < int(limits["per_month"]))

    return (all(checks) if checks else True), {
        "usage": {"per_minute": per_minute, "per_hour": per_hour, "by_day": by_day, "by_month": by_month},
        "limits": limits,
    }


def should_run(link: MeteoPointProvider, period_iso: str | None, mode: str, bucket: str, now: datetime) -> bool:
    """
    Достаточно ли времени прошло с последнего запуска по этому bucket.
    """
    if not period_iso:
        return False
    period = parse_iso_duration(period_iso)
    if not period or period.total_seconds() <= 0:
        return False

    last_at = parse_iso_utc(((link.status or {}).get(f"{mode}_{bucket}", {}) or {}).get("last_update"))
    if not last_at:
        return True
    return (now - last_at) >= period


def missing_date_ranges(qs, start_dt, end_dt, field_name="timestamp_utc", max_days_in_range=30):
    """
    Находит отсутствующие ДАТЫ в интервале [start_dt, end_dt] по полю `field_name`
    и объединяет их в непрерывные периоды. Затем режет периоды так, чтобы
    их длина не превышала `max_days_in_range` (по умолчанию 30 дней).
    Возвращает список периодов: [[date_start, date_end], ...].
    Если пропуск только один день — date_start == date_end.
    """
    if start_dt is None or end_dt is None:
        return []

    present_dates = set(
        qs.filter(**{f"{field_name}__gte": start_dt, f"{field_name}__lte": end_dt})
          .annotate(d=TruncDate(field_name))
          .values_list("d", flat=True)
          .distinct()
    )

    cur = start_dt.date()
    last = end_dt.date()
    ranges, run_start, prev = [], None, None
    one_day = timedelta(days=1)

    # Собираем непрерывные пропуски
    while cur <= last:
        if cur not in present_dates:
            if run_start is None:
                run_start = cur
            prev = cur
        else:
            if run_start is not None:
                ranges.append([run_start, prev])
                run_start = prev = None
        cur += one_day
    if run_start is not None:
        ranges.append([run_start, prev])

    # Режем длинные периоды на куски не длиннее max_days_in_range
    if not ranges:
        return []

    clipped = []
    span = max_days_in_range - 1
    for start_date, end_date in ranges:
        sub_start = start_date
        while sub_start <= end_date:
            sub_end = min(sub_start + timedelta(days=span), end_date)
            clipped.append([sub_start, sub_end])
            sub_start = sub_end + one_day

    return clipped
