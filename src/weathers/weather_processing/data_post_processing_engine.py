from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable

from django.utils import timezone as dj_tz

from weathers.models import (
    MeteoPointProvider,
    WeatherData,
    CalculatedIndicator,
)


UTC = timezone.utc


DAILY_TYPES = (
    WeatherData.DataType.HIST_DAY,
    WeatherData.DataType.FCT_DAY,
)
HOURLY_TYPES = (
    WeatherData.DataType.HIST_HR,
    WeatherData.DataType.FCT_HR,
)
MIN15_TYPES = (
    WeatherData.DataType.HIST_15,
    WeatherData.DataType.FCT_15,
)


def _to_start_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, tzinfo=UTC)


def _to_end_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)


def _daterange(d0: date, d1: date) -> Iterable[date]:
    step = (d1 - d0).days
    for n in range(step + 1):
        yield d0 + timedelta(days=n)


def _last_wins_by_ts(rows):
    """
    Убирает дубликаты
    """
    out = {}
    for r in rows:
        out[r["timestamp_utc"]] = r["value"]
    return out


@dataclass
class IndicatorResult:
    code: str
    params: dict
    value: dict


class PostProcessingEngine:
    """
    Собирает сохранённые ряды WeatherData и считает агрегаты/индикаторы.
    Сохраняет результат в CalculatedIndicator.
    """

    def __init__(self, mpp: MeteoPointProvider) -> None:
        self.mpp = mpp

    def run_all(
        self,
        start_date: date,
        end_date: date,
        *,
        t_base: float = 10.0,
        rh_threshold: float = 90.0,
        inf_t_min: float = 15.0,
        inf_t_max: float = 25.0,
        save: bool = True,
    ) -> Dict[str, dict]:
        results = {}
        results["gdd"] = self.compute_gdd(start_date, end_date, t_base=t_base, save=save)
        results["water_balance"] = self.compute_water_balance(start_date, end_date, save=save)
        results["chill_hours"] = self.compute_chill_hours(start_date, end_date, save=save)
        results["infection_index"] = self.compute_infection_index(
            start_date, end_date, rh_threshold=rh_threshold, t_min=inf_t_min, t_max=inf_t_max, save=save
        )
        results["radiation_total"] = self.compute_total_radiation(start_date, end_date, save=save)
        return results

    def compute_gdd(self, start_date: date, end_date: date, *, t_base: float = 10.0, save: bool = True) -> dict:
        """
        GDD_daily = max(0, T_mean - T_base), где T_mean = (T_max + T_min)/2.
        Если нет суточных T_max/T_min, берём дневное среднее из почасовой "temperature".
        """
        tmax = self._daily_series("temperature_max", start_date, end_date)
        tmin = self._daily_series("temperature_min", start_date, end_date)
        tmean = self._daily_series("temperature_mean", start_date, end_date)

        # fill mean from max/min if needed
        for d in _daterange(start_date, end_date):
            if d not in tmean:
                if d in tmax and d in tmin:
                    try:
                        tmean[d] = (float(tmax[d]) + float(tmin[d])) / 2.0
                    except Exception:
                        pass

        # fallback: hourly average per day
        missing_days = [d for d in _daterange(start_date, end_date) if d not in tmean]
        if missing_days:
            hourly = self._series_per_hour("temperature", min(missing_days), max(missing_days))
            by_day = {}
            for ts, v in hourly.items():
                d = ts.date()
                by_day.setdefault(d, []).append(float(v))
            for d in missing_days:
                if d in by_day and by_day[d]:
                    tmean[d] = sum(by_day[d]) / len(by_day[d])

        daily_rows = []
        total = 0.0
        for d in _daterange(start_date, end_date):
            tm = tmean.get(d)
            if tm is None:
                continue
            gdd = max(0.0, float(tm) - float(t_base))
            total += gdd
            daily_rows.append({"date": d.isoformat(), "t_mean": round(float(tm), 3), "gdd": round(gdd, 3)})

        value = {"params": {"t_base": t_base}, "daily": daily_rows, "total": round(total, 3)}
        if save:
            self._save_indicator("gdd", value, params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "t_base": t_base})
        return value

    def compute_water_balance(self, start_date: date, end_date: date, *, save: bool = True) -> dict:
        """
        Баланс по дням: deficit = et0_fao_evapotranspiration_sum - precipitation_sum.
        Накопленный баланс — сумма дефицитов/профицитов.
        """
        pr = self._daily_series("precipitation_sum", start_date, end_date)
        et0 = self._daily_series("et0_fao_evapotranspiration_sum", start_date, end_date)
        if not et0:
            et0 = self._daily_series("et0_fao_evapotranspiration", start_date, end_date)

        rows = []
        cum = 0.0
        for d in _daterange(start_date, end_date):
            p = float(pr.get(d, 0.0))
            e = float(et0.get(d, 0.0))
            deficit = e - p
            cum += deficit
            rows.append({"date": d.isoformat(), "precipitation_sum": round(p, 3), "et0_sum": round(e, 3), "deficit": round(deficit, 3), "cum_balance": round(cum, 3)})

        value = {"daily": rows, "total": round(cum, 3)}
        if save:
            self._save_indicator("water_balance", value, params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()})
        return value

    def compute_chill_hours(self, start_date: date, end_date: date, *, t_low: float = 0.0, t_high: float = 7.2, save: bool = True) -> dict:
        """
        Считает часы, когда t_low < T < t_high (по умолчанию 0..7.2°C).
        """
        hr = self._series_per_hour("temperature", start_date, end_date, include_min15=True)
        hours = []
        total = 0
        for ts, v in hr.items():
            t = float(v)
            if t_low < t < t_high:
                hours.append(ts.isoformat())
                total += 1
        value = {"params": {"t_low": t_low, "t_high": t_high}, "hours": hours, "total": total}
        if save:
            self._save_indicator("chill_hours", value, params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "t_low": t_low, "t_high": t_high})
        return value

    def compute_infection_index(self, start_date: date, end_date: date, *, rh_threshold: float = 90.0, t_min: float = 15.0, t_max: float = 25.0, save: bool = True) -> dict:
        """
        Простейший инфекционный индекс: число часов, когда RH >= rh_threshold и t_min <= T <= t_max.
        """
        t_series = self._series_per_hour("temperature", start_date, end_date, include_min15=True)
        rh_series = self._series_per_hour("relative_humidity", start_date, end_date, include_min15=True)

        stamps = sorted(set(t_series.keys()) | set(rh_series.keys()))
        hours = []
        total = 0
        for ts in stamps:
            if ts in t_series and ts in rh_series:
                t = float(t_series[ts])
                rh = float(rh_series[ts])
                if t_min <= t <= t_max and rh >= rh_threshold:
                    hours.append(ts.isoformat())
                    total += 1

        value = {"params": {"rh_threshold": rh_threshold, "t_min": t_min, "t_max": t_max}, "hours": hours, "total": total}
        if save:
            self._save_indicator("infection_index", value, params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "rh_threshold": rh_threshold, "t_min": t_min, "t_max": t_max})
        return value

    def compute_total_radiation(self, start_date: date, end_date: date, *, save: bool = True) -> dict:
        """
        Σ(shortwave_radiation_sum) за период.
        Единицы зависят от источника (Open‑Meteo — обычно МДж/м²).
        """
        r = self._daily_series("shortwave_radiation_sum", start_date, end_date)
        rows = [{"date": d.isoformat(), "shortwave_radiation_sum": round(float(r.get(d, 0.0)), 4)} for d in _daterange(start_date, end_date)]
        total = sum(float(r.get(d, 0.0)) for d in _daterange(start_date, end_date))
        value = {"daily": rows, "total": round(total, 4)}
        if save:
            self._save_indicator("radiation_total", value, params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()})
        return value

    def _daily_series(self, param: str, start_date: date, end_date: date) -> Dict[date, float]:
        start_dt = _to_start_dt(start_date)
        end_dt = _to_end_dt(end_date)
        qs = (
            WeatherData.objects
            .filter(
                meteo_point_provider=self.mpp,
                parameter=param,
                data_type__in=DAILY_TYPES,
                timestamp_utc__gte=start_dt,
                timestamp_utc__lte=end_dt,
            )
            .order_by("timestamp_utc", "created_at")
            .values("timestamp_utc", "value")
        )
        by_ts = _last_wins_by_ts(qs)
        by_day: Dict[date, float] = {}
        for ts, val in by_ts.items():
            by_day[ts.date()] = float(val)
        return by_day

    def _series_per_hour(
        self,
        param: str,
        start_date: date,
        end_date: date,
        *,
        include_min15: bool = False,
    ) -> Dict[datetime, float]:
        start_dt = _to_start_dt(start_date)
        end_dt = _to_end_dt(end_date)

        types = list(HOURLY_TYPES)
        if include_min15:
            types += list(MIN15_TYPES)

        qs = (
            WeatherData.objects
            .filter(
                meteo_point_provider=self.mpp,
                parameter=param,
                data_type__in=types,
                timestamp_utc__gte=start_dt,
                timestamp_utc__lte=end_dt,
            )
            .order_by("timestamp_utc", "created_at")
            .values("timestamp_utc", "value")
        )
        return _last_wins_by_ts(qs)

    def _save_indicator(self, code: str, value: dict, *, params: dict) -> CalculatedIndicator:
        now = dj_tz.now()
        obj = CalculatedIndicator.objects.create(
            meteo_point_provider=self.mpp,
            indicator_code=code,
            value=value,
            calculated_at=now,
            params=params or {},
        )
        return obj
