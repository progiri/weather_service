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

    def __init__(self, api_url: str, credentials: dict, timeout: int = 10, archive_api_url: str = None) -> None:
        self.api_url = api_url.rstrip("/")
        self.archive_api_url = archive_api_url.rstrip("/") if archive_api_url else api_url.rstrip("/")
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

    def stream_to_bytes(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        chunk_size: int = 1_048_576,  # 1 MiB
        max_attempts: int = 5,
        allow_resume: bool = True,
        timeout: Optional[tuple[int, int]] = None,  # (connect, read)
    ) -> str | bytes:
        """
        Универсальная стрим-закачка.
        """
        import time

        sess = self.http_session or requests.Session()
        self.http_session = sess

        base_headers = {
            "Accept-Encoding": "identity",
            "Connection": "close",
            **self._build_auth_header(),
        }
        if headers:
            base_headers.update(headers)

        timeout = timeout or (self.timeout, max(self.timeout, 120))
        downloaded = 0
        buf = bytearray()
        attempts = 0

        while attempts < max_attempts:
            req_headers = dict(base_headers)
            if allow_resume and downloaded:
                req_headers["Range"] = f"bytes={downloaded}-"

            try:
                log.debug(
                    "STREAM %s %s params=%s headers=%s",
                    method, url, params,
                    {k: v for k, v in req_headers.items() if
                     k.lower() != "authorization"},
                )
                with sess.request(
                        method,
                        url,
                        params=params,
                        headers=req_headers,
                        timeout=timeout,
                        stream=True,
                ) as resp:
                    if resp.status_code not in (200, 206):
                        self.update_provider_token_stats(resp)
                        resp.raise_for_status()

                    if resp.status_code == 200 and downloaded:
                        buf = bytearray()
                        downloaded = 0

                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if chunk:
                            buf.extend(chunk)
                            downloaded += len(chunk)

                    self.update_provider_token_stats(resp)
                    return bytes(buf)

            except (requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.ReadTimeout) as e:
                attempts += 1
                sleep_s = min(2 ** attempts, 30)
                log.warning(
                    "Stream error (%s). Attempt %d/%d. Sleeping %ss. url=%s",
                    e.__class__.__name__, attempts, max_attempts, sleep_s, url
                )
                time.sleep(sleep_s)
                continue

        raise RuntimeError(f"Streaming failed after {max_attempts} attempts: {url}")

    def _build_auth_header(self) -> dict[str, str]:
        """
        Стандартный «Authorization: Bearer …». Адаптер может переопределить.
        """
        return {}

    def update_provider_token_stats(self, resp: requests.Response) -> None:
        pass

    @staticmethod
    def parse_json(resp, stream: bool = False) -> Mapping[str, Any]:
        """
        Безопасный json-разбор с логированием ошибок.
        """
        try:
            if stream:
                return json.loads(resp)
            return resp.json()
        except json.JSONDecodeError as exc:
            log.error("Invalid JSON %s: %s…", resp.url, resp.text[:200])
            raise RuntimeError("Provider returned invalid JSON") from exc
