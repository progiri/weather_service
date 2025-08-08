# providers/open_meteo.py
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Mapping, Optional

from .base_interface import BaseProviderInterface

log = logging.getLogger(__name__)


class OpenMeteoInterface(BaseProviderInterface):
    DEFAULT_FORECAST_DAYS = 7
    SUPPORTED_GRANULARITY = {"hourly", "daily", "minutely_15"}

    def __init__(
        self,
        api_url: str = "https://api.open-meteo.com/v1",
        credentials: Optional[dict] = None,
        timeout: int = 10,
    ) -> None:
        super().__init__(api_url=api_url, credentials=credentials or dict(api_key=""), timeout=timeout)

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

        if date_from:
            params["start_date"] = date_from.isoformat()
        if date_to:
            params["end_date"] = date_to.isoformat()
        elif date_from:
            params["end_date"] = (date_from + self._forecast_horizon()).isoformat()

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
        pass
