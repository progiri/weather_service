from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from django.utils import timezone
from typing import Any, Mapping, Optional, Dict
from django.db import transaction
from .base_interface import BaseProviderInterface
from weathers.models import ProviderTokenStat, ProviderToken, Provider

log = logging.getLogger(__name__)


def _bump_rolling_window(win: Dict[str, Any], now: datetime, seconds: int) -> Dict[str, Any]:
    """Счётчик для скользящего окна (per_minute/per_hour)."""
    start_iso = win.get("start")
    try:
        start = datetime.fromisoformat(start_iso) if start_iso else None
        if start and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
    except Exception:
        start = None
    if not start or (now - start).total_seconds() >= seconds:
        win = {"start": now.isoformat(), "count": 0}
    win["count"] = int(win.get("count", 0)) + 1
    return win


class OpenMeteoInterface(BaseProviderInterface):
    DEFAULT_FORECAST_DAYS = 7
    SUPPORTED_GRANULARITY = {"hourly", "daily", "minutely_15"}

    def __init__(
        self,
        provider: Provider,
        provider_token: ProviderToken,
    ) -> None:
        self.provider = provider
        self.provider_token = provider_token
        api_url = provider.config.get("api_url", "https://api.open-meteo.com/v1")
        super().__init__(api_url=api_url, credentials={} or dict(api_key=""), timeout=10)

    def get_forecast(
        self,
        lat: float,
        lon: float,
        parameters: list[str],
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        granularity: str = "hourly",
    ) -> Mapping[str, Any]:
        self._validate_granularity(granularity)

        endpoint = f"{self.api_url}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            granularity: ",".join(parameters),
            "timezone": "UTC",
        }

        now_date = datetime.now().date()

        if date_from:
            params["past_days"] = str((now_date - date_from).days)
        if date_to:
            params["forecast_days"] = str((date_to - now_date).days)
        elif date_from:
            params["forecast_days"] = str(((date_from + self._forecast_horizon()) - now_date).days)

        resp = self.send_request("GET", endpoint, params=params)
        return self.parse_json(resp)

    def get_history(
        self,
        lat: float,
        lon: float,
        parameters: list[str],
        date_from: date,
        date_to: date,
        granularity: str = "hourly",
    ) -> Mapping[str, Any]:
        self._validate_granularity(granularity)

        endpoint = f"{self.api_url}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            granularity: ",".join(parameters),
            "start_date": date_from.isoformat(),
            "end_date": date_to.isoformat(),
            "timezone": "UTC",
        }

        resp = self.send_request("GET", endpoint, params=params)
        return self.parse_json(resp)

    @staticmethod
    def _forecast_horizon():
        from datetime import timedelta
        return timedelta(days=OpenMeteoInterface.DEFAULT_FORECAST_DAYS)

    def _validate_granularity(self, granularity: str) -> None:
        if granularity not in self.SUPPORTED_GRANULARITY:
            raise ValueError(
                f"Open-Meteo supports only {self.SUPPORTED_GRANULARITY}, got '{granularity}'"
            )

    def update_provider_token_stats(self, resp):
        """
        Обновляет счётчики использования токена и флаги превышения лимитов.
        Ожидается credentials={"token_id": <id ProviderToken>}.
        """
        now = timezone.now()
        day_key = now.strftime("%Y-%m-%d")
        month_key = now.strftime("%Y-%m")

        with transaction.atomic():
            stat, _ = ProviderTokenStat.objects.select_for_update().get_or_create(
                token=self.provider_token, defaults={"meta": {}}
            )
            meta: Dict[str, Any] = stat.meta or {}
            usage: Dict[str, Any] = meta.get("usage") or {}

            usage["total"] = int(usage.get("total", 0)) + 1

            by_day = usage.get("by_day") or {}
            by_day[day_key] = int(by_day.get(day_key, 0)) + 1
            usage["by_day"] = by_day

            by_month = usage.get("by_month") or {}
            by_month[month_key] = int(by_month.get(month_key, 0)) + 1
            usage["by_month"] = by_month

            usage["per_minute"] = _bump_rolling_window(usage.get("per_minute") or {}, now, 60)
            usage["per_hour"]   = _bump_rolling_window(usage.get("per_hour")   or {}, now, 3600)

            usage["last_status"] = getattr(resp, "status_code", None)
            usage["last_url"] = getattr(resp, "url", None)
            usage["last_at"] = now.isoformat()

            limits: Dict[str, Any] = meta.get("limits") or {}
            try:
                prov_limits = (self.provider_token.provider.config or {}).get("limits") or {}
                if prov_limits:
                    limits.update(prov_limits)
            except ProviderToken.DoesNotExist:
                pass

            exceeded = {}
            if "per_minute" in limits:
                exceeded["per_minute"] = usage["per_minute"]["count"] >= int(limits["per_minute"])
            if "per_hour" in limits:
                exceeded["per_hour"] = usage["per_hour"]["count"] >= int(limits["per_hour"])
            if "per_day" in limits:
                exceeded["per_day"] = by_day[day_key] >= int(limits["per_day"])
            if "per_month" in limits:
                exceeded["per_month"] = by_month[month_key] >= int(limits["per_month"])

            meta["usage"] = usage
            if limits:
                meta["limits"] = limits
                meta["exceeded"] = exceeded

            if len(by_day) > 150:
                for k in sorted(by_day.keys())[:-120]:
                    by_day.pop(k, None)
            if len(by_month) > 30:
                for k in sorted(by_month.keys())[:-24]:
                    by_month.pop(k, None)

            stat.meta = meta
            stat.save(update_fields=["meta", "updated_at"])
