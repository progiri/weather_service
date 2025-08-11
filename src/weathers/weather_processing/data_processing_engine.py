from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from django.db import transaction

from weathers.models import MeteoPointProvider, WeatherData
from weathers.lib.data_normalizer import DataNormalizer
from weathers.interfaces.open_meteo_interface import OpenMeteoInterface
from weathers.lib.param_catalog import OPEN_METEO_PARAM_CATALOG

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchPlan:
    """Что тянуть и как это потом помечать в БД."""
    granularity: str                    # "hourly" | "daily" | "minutely_15"
    parameters_provider: List[str]      # имена переменных провайдера для этой секции
    data_type_forecast: str             # WeatherData.DataType.*
    data_type_history: str              # WeatherData.DataType.*


_DAILY_CANON = {
    "temperature_max", "temperature_mean", "temperature_min",
    "apparent_temperature_max", "apparent_temperature_mean", "apparent_temperature_min",
    "precipitation_sum", "rain_sum", "showers_sum", "snowfall_sum",
    "precipitation_hours",
    "precipitation_probability_max", "precipitation_probability_mean", "precipitation_probability_min",
    "sunrise", "sunset", "daylight_duration",
    "uv_index_max", "uv_index_clear_sky_max",
    "wind_speed_10m_max", "wind_gusts_10m_max", "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration_sum",
}

_MINUTELY15_CANON = {
    "temperature", "relative_humidity", "dew_point", "apparent_temperature",
    "wind_speed_10m", "wind_speed_80m",
    "wind_direction_10m", "wind_direction_80m",
    "wind_gusts_10m",
    "precipitation", "rain", "showers", "snowfall", "snowfall_height",
    "visibility", "cape", "lightning_potential", "is_day", "weather_code",
    "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    "direct_normal_irradiance", "global_tilted_irradiance",
    "global_tilted_irradiance_instant",
    "sunshine_duration",
}

_ALL_CANON = {k for k, v in OPEN_METEO_PARAM_CATALOG.items() if v.get("open_meteo")}
_HOURLY_CANON = sorted((_ALL_CANON - _DAILY_CANON) - {"date_time"})


def _canon_to_provider(keys: Iterable[str]) -> List[str]:
    """Преобразовать канонические имена в имена для Open-Meteo."""
    res: List[str] = []
    for k in keys:
        meta = OPEN_METEO_PARAM_CATALOG.get(k) or {}
        src = meta.get("open_meteo")
        if src:
            res.append(src)
    seen = set()
    uniq: List[str] = []
    for x in res:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _build_default_plan(sections: Sequence[str]) -> List[FetchPlan]:
    plans: List[FetchPlan] = []
    for sec in sections:
        if sec == "hourly":
            plans.append(
                FetchPlan(
                    granularity="hourly",
                    parameters_provider=_canon_to_provider(_HOURLY_CANON),
                    data_type_forecast=WeatherData.DataType.FCT_HR,
                    data_type_history=WeatherData.DataType.HIST_HR,
                )
            )
        elif sec == "daily":
            plans.append(
                FetchPlan(
                    granularity="daily",
                    parameters_provider=_canon_to_provider(sorted(_DAILY_CANON)),
                    data_type_forecast=WeatherData.DataType.FCT_DAY,
                    data_type_history=WeatherData.DataType.HIST_DAY,
                )
            )
        elif sec == "minutely_15":
            plans.append(
                FetchPlan(
                    granularity="minutely_15",
                    parameters_provider=_canon_to_provider(sorted(_MINUTELY15_CANON)),
                    data_type_forecast=WeatherData.DataType.FCT_15,
                    data_type_history=WeatherData.DataType.HIST_15,
                )
            )
        else:
            raise ValueError(f"Unknown section '{sec}'")
    return plans


class DataProcessEngine:
    """
    Тянет у провайдера (пока 'open_meteo'), нормализует и сохраняет в WeatherData.
    Работает в двух режимах: forecast / history. Для history требует date_from/date_to.
    """

    def __init__(
        self,
        *,
        meteo_point_provider: MeteoPointProvider,
        mode: str,  # "forecast" | "history"
        normalizer: Optional[DataNormalizer] = None,
        sections: Sequence[str] = ("hourly", "daily", "minutely_15"),
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        overwrite: bool = True,
        save_batch: int = 1000,
    ) -> None:
        if mode not in {"forecast", "history"}:
            raise ValueError("mode must be 'forecast' or 'history'")
        if mode == "history" and (not date_from or not date_to):
            raise ValueError("history mode requires date_from and date_to")

        self.point = meteo_point_provider.meteo_point
        self.provider = meteo_point_provider.provider
        self.mode = mode
        self.date_from = date_from
        self.date_to = date_to
        self.overwrite = overwrite
        self.save_batch = save_batch

        self.normalizer = normalizer or DataNormalizer()
        self.plans = _build_default_plan(sections)

        if self.provider.code != "open_meteo":
            raise NotImplementedError(f"Provider '{self.provider.code}' is not supported yet")

        self.adapter = OpenMeteoInterface(provider=self.provider)

    def process(self) -> Dict[str, object]:
        """
        Пробегает по гранулярностям, тянет данные, нормализует и сохраняет.
        Возвращает сводку по вставкам.
        """
        summary: Dict[str, int] = {}
        for plan in self.plans:
            raw = self._fetch(plan)
            std = self._standardize(raw, plan.granularity)
            count = self._save_narrow(std, plan)
            summary[plan.granularity] = count

        return {
            "meteo_point_id": self.point.pk,
            "provider": self.provider.code,
            "mode": self.mode,
            "inserted": summary,
        }

    def _fetch(self, plan: FetchPlan) -> Mapping[str, object]:
        lat = float(self.point.point.y)
        lon = float(self.point.point.x)

        if self.mode == "forecast":
            raw = self.adapter.get_forecast(
                lat=lat,
                lon=lon,
                parameters=plan.parameters_provider,
                date_from=self.date_from,
                date_to=self.date_to,
                granularity=plan.granularity,
            )
        else:
            raw = self.adapter.get_history(
                lat=lat,
                lon=lon,
                parameters=plan.parameters_provider,
                date_from=self.date_from,
                date_to=self.date_to,
                granularity=plan.granularity,
            )
        return raw

    def _standardize(self, payload: Mapping[str, object], granularity: str) -> Dict[str, List[Dict[str, object]]]:
        return self.normalizer.open_meteo_standardize(dict(payload), sections=(granularity,))

    def _save_narrow(self, standardized: Dict[str, List[Dict[str, object]]], plan: FetchPlan) -> int:
        rows = standardized.get(plan.granularity) or []
        if not rows:
            return 0

        t_min, t_max = _span(rows)
        data_type = plan.data_type_forecast if self.mode == "forecast" else plan.data_type_history

        if self.overwrite and (t_min and t_max):
            with transaction.atomic():
                qs = WeatherData.objects.filter(
                    meteo_point=self.point,
                    data_type=data_type,
                    timestamp_utc__gte=t_min,
                    timestamp_utc__lte=t_max,
                )
                qs.delete()

        objs: List[WeatherData] = []
        for r in rows:
            ts = _parse_iso_utc(r.get("date_time"))
            if not ts:
                continue
            for k, v in r.items():
                if k == "date_time" or v is None:
                    continue
                objs.append(
                    WeatherData(
                        meteo_point=self.point,
                        parameter=k,
                        timestamp_utc=ts,
                        value=v,
                        data_type=data_type,
                    )
                )

        inserted = 0
        with transaction.atomic():
            for chunk in _chunks(objs, self.save_batch):
                WeatherData.objects.bulk_create(chunk, batch_size=self.save_batch)
                inserted += len(chunk)

        return inserted


def _parse_iso_utc(v: object) -> Optional[datetime]:
    """
    Преобразует вход к aware-UTC datetime.
    Поддерживает:
      - datetime/date объекты
      - ISO-строки: YYYY-MM-DD[ T]HH:MM[:SS[.us]][(+|-)HH:MM] и варианты c 'Z'
      - только дату YYYY-MM-DD (берём 00:00:00)
      - эпоху в секундах/миллисекундах (int/float/цифровая строка)
    Наивные даты считаем UTC.
    """
    # 1) Уже datetime/date
    if isinstance(v, datetime):
        dt = v
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day, tzinfo=timezone.utc)

    # 2) Эпоха (seconds / milliseconds)
    if isinstance(v, (int, float)):
        try:
            # эвристика: большие числа считаем миллисекундами
            ts = float(v) / 1000.0 if abs(v) >= 1_000_000_000_000 else float(v)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None

    # 3) Строки
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None

        # 3a) Эпоха как строка из цифр
        if s.isdigit():
            try:
                iv = int(s)
                ts = iv / 1000.0 if iv >= 1_000_000_000_000 else iv
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass

        # 3b) Нормализация 'Z' (UTC)
        force_utc = False
        if s.endswith("Z"):
            s = s[:-1]
            force_utc = True

        # 3c) Прямой разбор ISO через fromisoformat (понимает и ' ' вместо 'T')
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc if force_utc else timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            # 3d) Возможно, это только дата
            try:
                d = date.fromisoformat(s)
                return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            except ValueError:
                pass

            # 3e) Пара частых fallback-форматов без таймзоны
            for fmt in ("%Y-%m-%d %H:%M",
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S.%f",
                        "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    dt = datetime.strptime(s, fmt)
                    return dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

        return None

    # 4) Иные типы — не поддерживаем
    return None


def _chunks(seq: Iterable[WeatherData], size: int) -> Iterable[List[WeatherData]]:
    buf: List[WeatherData] = []
    for x in seq:
        buf.append(x)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def _span(rows: List[Dict[str, object]]) -> Tuple[Optional[datetime], Optional[datetime]]:
    times: List[datetime] = []
    for r in rows:
        ts = _parse_iso_utc(r.get("time"))
        if ts:
            times.append(ts)
    if not times:
        return None, None
    return min(times), max(times)

