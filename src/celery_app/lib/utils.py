from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple

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
