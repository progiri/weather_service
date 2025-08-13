from __future__ import annotations

import logging
from typing import Dict

from django.utils import timezone as django_timezone

from weathers.models import (
    MeteoPointProvider,
    ProviderToken, WeatherData,
)
from celery_app.lib.utils import (
    token_has_capacity,
    should_run,
)
from celery_app import app
from weathers.weather_processing.data_processing_engine import DataProcessEngine

log = logging.getLogger(__name__)


@app.task(bind=True)
def task_auto_start_meteo_data_process(self):
    now = django_timezone.now()

    meteo_point_providers = (
        MeteoPointProvider.objects.select_related("provider", "meteo_point")
        .filter(is_active=True, provider__is_active=True, meteo_point__is_active=True)
    )
    stats = {
        "checked": 0,
        "skipped_busy": 0,
        "skipped_limits": 0,
        "skipped_period": 0,
        "dispatched": 0,
        "ts": now.isoformat(),
    }

    for mpp in meteo_point_providers.iterator():
        provider = mpp.provider
        sched = (provider.update_schedule or {}).get("periods", {})
        stats["checked"] += 1

        # подобрать токен с запасом по лимитам
        has_capacity = True
        token_id: int | None = None
        tokens = list(provider.tokens.filter(is_active=True))
        if tokens:
            has_capacity = False
            for t in tokens:
                has, _ = token_has_capacity(t, now)
                if has:
                    has_capacity = True
                    token_id = t.id
                    break

        if not has_capacity:
            stats["skipped_limits"] += 1
            continue

        for bucket in ("hourly", "daily"):
            period_iso = sched.get(bucket)
            if not period_iso:
                continue

            if not should_run(mpp, period_iso, "forecast", bucket, now):
                stats["skipped_period"] += 1
                continue
            print("sending to processing")
            task_parse_provider_meteo_forecast_data.apply_async([mpp.id, bucket, token_id])

    # for mpp in meteo_point_providers.iterator():
    #     task_parse_provider_meteo_history_data.apply_async([mpp.id, token_id])


@app.task(bind=True)
def task_parse_provider_meteo_forecast_data(self, meteo_point_provider_id, bucket, provider_token_id) -> Dict:
    mpp = MeteoPointProvider.objects.get(id=meteo_point_provider_id)
    provider_token = ProviderToken.objects.get(id=provider_token_id)
    engine = DataProcessEngine(
        meteo_point_provider=mpp,
        provider_token=provider_token,
        mode="forecast",
        sections=(bucket,)
    )
    print(engine.process())

