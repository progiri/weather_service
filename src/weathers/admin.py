from django.contrib import admin

from .models import (
    Provider,
    ProviderToken,
    ProviderTokenStat,
    MeteoPoint,
    MeteoPointProvider,
    PointsOfInterest,
    WeatherData,
    CalculatedIndicator,
)


admin.site.register(Provider)
admin.site.register(ProviderToken)
admin.site.register(ProviderTokenStat)
admin.site.register(MeteoPoint)
admin.site.register(MeteoPointProvider)
admin.site.register(PointsOfInterest)
admin.site.register(WeatherData)
admin.site.register(CalculatedIndicator)
