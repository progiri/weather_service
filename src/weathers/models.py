from django.db import models
from django.db.models import JSONField
from django.contrib.postgres.indexes import GistIndex
from django.contrib.gis.db import models as gis_models
from django.utils.translation import gettext_lazy as _


class Provider(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Код провайдера"))
    name = models.CharField(max_length=255, verbose_name=_("Название провайдера"))
    is_active = models.BooleanField(default=True, verbose_name=_("Активен"))
    config = JSONField(blank=True, default=dict, verbose_name=_("Конфигурация"))
    update_schedule = JSONField(blank=True, default=dict, verbose_name=_("Расписание обновлений"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Дата создания"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Дата обновления"))

    class Meta:
        verbose_name = _("Провайдер данных")
        verbose_name_plural = _("Провайдеры данных")

    def __str__(self):
        return self.name

    def get_token(self):
        return self.tokens.first()


class ProviderToken(models.Model):
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="tokens",
        verbose_name=_("Провайдер"),
    )
    credentials = JSONField(verbose_name=_("Учётные данные"))
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Срок действия"))
    is_active = models.BooleanField(default=True, verbose_name=_("Активен"))

    class Meta:
        verbose_name = _("Токен провайдера")
        verbose_name_plural = _("Токены провайдеров")

    def __str__(self):
        return f"{self.provider.code}:{self.pk}"


class ProviderTokenStat(models.Model):
    token = models.ForeignKey(
        ProviderToken,
        on_delete=models.CASCADE,
        related_name="stats",
        verbose_name=_("Токен"),
    )
    meta = JSONField(blank=True, default=dict, verbose_name=_("Метаданные"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Создано"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Обновлено"))

    class Meta:
        verbose_name = _("Статистика токена")
        verbose_name_plural = _("Статистика токенов")

    def __str__(self):
        return f"Stats for {self.token_id}"


class MeteoPoint(models.Model):
    point = gis_models.PointField(verbose_name=_("Координаты точки"))
    timezone = models.CharField(max_length=100, verbose_name=_("Часовой пояс"))
    search_radius_m = models.PositiveIntegerField(default=5000, verbose_name=_("Радиус привязки, м"))
    is_active = models.BooleanField(default=True, verbose_name=_("Активна"))
    last_fetch_status = models.CharField(max_length=50, null=True, blank=True, verbose_name=_("Статус последней загрузки"))
    last_fetched_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Последняя успешная загрузка"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Создано"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Обновлено"))

    class Meta:
        indexes = [
            models.Index(fields=["last_fetched_at"]),
            GistIndex(fields=["point"]),
        ]
        verbose_name = _("Метео-точка")
        verbose_name_plural = _("Метео-точки")


class MeteoPointProvider(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, verbose_name=_("Провайдер"))
    meteo_point = models.ForeignKey(MeteoPoint, on_delete=models.CASCADE, verbose_name=_("Метео-точка"))
    status = JSONField(blank=True, default=dict, verbose_name=_("Статус"))
    is_active = models.BooleanField(default=True, verbose_name=_("Активен"))

    class Meta:
        unique_together = ("provider", "meteo_point")
        verbose_name = _("Связь метео-точка ↔ провайдер")
        verbose_name_plural = _("Связи метео-точка ↔ провайдер")

    def __str__(self):
        return f"{self.meteo_point_id} ⇄ {self.provider.code}"


class PointsOfInterest(models.Model):
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="point_of_interests",
        verbose_name=_("Компания"),
    )
    meteo_point = models.ForeignKey(
        MeteoPoint,
        on_delete=models.CASCADE,
        related_name="point_of_interests",
        verbose_name=_("Метео-точка"),
    )
    title = models.CharField(max_length=255, verbose_name=_("Название"))
    point = gis_models.PointField(verbose_name=_("Координаты"))
    is_active = models.BooleanField(default=True, verbose_name=_("Активна"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Создано"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Обновлено"))

    class Meta:
        indexes = [
            models.Index(fields=["company", "is_active"]),
            models.Index(fields=["meteo_point"]),
            GistIndex(fields=["point"]),
        ]
        verbose_name = _("Точка интереса")
        verbose_name_plural = _("Точки интереса")

    def __str__(self):
        return self.title


class WeatherData(models.Model):
    class DataType(models.TextChoices):
        FCT_15 = "forecast_15m", _("Прогноз 15 мин")
        FCT_HR = "forecast_hourly", _("Прогноз почасовой")
        FCT_DAY = "forecast_daily", _("Прогноз дневной")
        HIST_15 = "history_15m", _("История 15 мин")
        HIST_HR = "history_hourly", _("История почасовая")
        HIST_DAY = "history_daily", _("История дневная")

    meteo_point = models.ForeignKey(
        MeteoPoint,
        on_delete=models.CASCADE,
        related_name="weather_data",
        verbose_name=_("Метео-точка"),
    )
    parameter = models.CharField(
        max_length=255,
        verbose_name=_("Параметр"),
    )
    timestamp_utc = models.DateTimeField(verbose_name=_("Время (UTC)"))
    value = JSONField(verbose_name=_("Значение"))
    data_type = models.CharField(max_length=20, choices=DataType.choices, verbose_name=_("Тип данных"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Загружено"))

    class Meta:
        indexes = [
            models.Index(fields=["meteo_point", "timestamp_utc"]),
            models.Index(fields=["parameter", "timestamp_utc"]),
        ]
        verbose_name = _("Погодные данные")
        verbose_name_plural = _("Погодные данные")

    def __str__(self):
        return f"{self.meteo_point_id} {self.parameter} {self.timestamp_utc}"


class CalculatedIndicator(models.Model):
    meteo_point_provider = models.ForeignKey(
        MeteoPointProvider,
        on_delete=models.CASCADE,
        related_name="indicators",
        verbose_name=_("Связь метео-точка ↔ провайдер"),
    )
    indicator_code = models.CharField(max_length=100, verbose_name=_("Код показателя"))
    value = JSONField(verbose_name=_("Значение"))
    calculated_at = models.DateTimeField(verbose_name=_("Дата расчёта"))
    params = JSONField(blank=True, default=dict, verbose_name=_("Параметры"))

    class Meta:
        verbose_name = _("Агро-показатель")
        verbose_name_plural = _("Агро-показатели")

    def __str__(self):
        return f"{self.indicator_code} for {self.meteo_point_provider}"
