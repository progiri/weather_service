from __future__ import annotations

import abc
import json
import logging
from datetime import date
from typing import Any, Mapping, Optional

import requests

log = logging.getLogger(__name__)


class BaseProviderInterface(abc.ABC):
    """
    Базовый интерфейс для всех адаптеров метео-провайдеров.

    • Каждый конкретный провайдер наследуется от этого класса.
    • Если метод не переопределён → NotImplementedError.
    • Все даты/время — **UTC**; тайм-зона коррекции делается выше по стеку.
    """

    api_url: str
    credentials: dict
    timeout: int = 10
    http_session: Optional[requests.Session] = None

    def __init__(self, api_url: str, credentials: dict, timeout: int = 10) -> None:
        self.api_url = api_url.rstrip("/")
        self.credentials = credentials
        self.timeout = timeout
        self.http_session = None

    @abc.abstractmethod
    def get_forecast(
        self,
        lat: float,
        lon: float,
        parameters: list[str],
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        granularity: str = "hourly",
    ) -> Mapping[str, Any]:
        """
        Запрашивает прогноз. Диапазон дат обычно «сегодня+X дней».
        """

    @abc.abstractmethod
    def get_history(
        self,
        lat: float,
        lon: float,
        parameters: list[str],
        date_from: date,
        date_to: date,
        granularity: str = "hourly",
    ) -> Mapping[str, Any]:
        """
        Запрашивает архивные данные. Обязателен closed-interval `[date_from, date_to]`.
        """

    def send_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Базовый HTTP wrap. Добавляет заголовок авторизации, пишет debug-лог,
        осуществляет единственный retry при timeout.
        """
        sess = self.http_session or requests.Session()
        self.http_session = sess

        headers = kwargs.pop("headers", {})
        headers.update(self._build_auth_header())
        try:
            log.debug("HTTP %s %s  params=%s", method, url, kwargs.get("params"))
            resp = sess.request(method, url, timeout=self.timeout, headers=headers, **kwargs)
        except requests.Timeout:
            log.warning("HTTP timeout, repeat once: %s %s", method, url)
            resp = sess.request(method, url, timeout=self.timeout, headers=headers, **kwargs)

        self.update_provider_token_stats(resp)
        resp.raise_for_status()
        return resp

    def _build_auth_header(self) -> dict[str, str]:
        """
        Стандартный «Authorization: Bearer …». Адаптер может переопределить.
        """
        return {}

    def update_provider_token_stats(self, resp: requests.Response) -> None:
        pass

    @staticmethod
    def parse_json(resp: requests.Response) -> Mapping[str, Any]:
        """
        Безопасный json-разбор с логированием ошибок.
        """
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            log.error("Invalid JSON %s: %s…", resp.url, resp.text[:200])
            raise RuntimeError("Provider returned invalid JSON") from exc
