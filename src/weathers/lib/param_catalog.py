OPEN_METEO_PARAM_CATALOG: dict[str, dict[str, str | None]] = {
    # ─────────────―― 2-метровый уровень ─────────────――
    "date_time":            {"unit": None,   "desc_ru": "Дата и время",            "open_meteo": "time"},
    "temperature":          {"unit": "°C", "desc_ru": "Температура воздуха (2 м)", "open_meteo": "temperature_2m"},
    "relative_humidity":    {"unit": "%",  "desc_ru": "Отн. влажность (2 м)",      "open_meteo": "relative_humidity_2m"},
    "dew_point":            {"unit": "°C", "desc_ru": "Точка росы (2 м)",          "open_meteo": "dew_point_2m"},
    "apparent_temperature": {"unit": "°C", "desc_ru": "Ощущаемая темп-ра",         "open_meteo": "apparent_temperature"},

    # ─────────────―― Давление ―――――――――――――――――――
    "pressure_msl":     {"unit": "hPa", "desc_ru": "Давление на уровне моря", "open_meteo": "pressure_msl"},
    "surface_pressure": {"unit": "hPa", "desc_ru": "Давление у поверхности",  "open_meteo": "surface_pressure"},

    # ─────────────―― Облачность ―――――――――――――――――
    "cloud_cover":      {"unit": "%", "desc_ru": "Облачность общая",     "open_meteo": "cloud_cover"},
    "cloud_cover_low":  {"unit": "%", "desc_ru": "Нижний ярус облаков",  "open_meteo": "cloud_cover_low"},
    "cloud_cover_mid":  {"unit": "%", "desc_ru": "Средний ярус облаков", "open_meteo": "cloud_cover_mid"},
    "cloud_cover_high": {"unit": "%", "desc_ru": "Верхний ярус облаков", "open_meteo": "cloud_cover_high"},

    # ─────────────―― Ветер (10/80/120/180 м) ―――――――――
    "wind_speed_10m":      {"unit": "m/s", "desc_ru": "Скорость ветра 10 м",  "open_meteo": "wind_speed_10m"},
    "wind_speed_80m":      {"unit": "m/s", "desc_ru": "Скорость ветра 80 м",  "open_meteo": "wind_speed_80m"},
    "wind_speed_120m":     {"unit": "m/s", "desc_ru": "Скорость ветра 120 м", "open_meteo": "wind_speed_120m"},
    "wind_speed_180m":     {"unit": "m/s", "desc_ru": "Скорость ветра 180 м", "open_meteo": "wind_speed_180m"},
    "wind_direction_10m":  {"unit": "°",   "desc_ru": "Напр. ветра 10 м",     "open_meteo": "wind_direction_10m"},
    "wind_direction_80m":  {"unit": "°",   "desc_ru": "Напр. ветра 80 м",     "open_meteo": "wind_direction_80m"},
    "wind_direction_120m": {"unit": "°",   "desc_ru": "Напр. ветра 120 м",    "open_meteo": "wind_direction_120m"},
    "wind_direction_180m": {"unit": "°",   "desc_ru": "Напр. ветра 180 м",    "open_meteo": "wind_direction_180m"},
    "wind_gusts_10m":      {"unit": "m/s", "desc_ru": "Порывы ветра 10 м",    "open_meteo": "wind_gusts_10m"},

    # ─────────────―― Радиация и солнечное ――――――――――
    "shortwave_radiation":              {"unit": "W/m²", "desc_ru": "Суммарная солнечная",      "open_meteo": "shortwave_radiation"},
    "direct_radiation":                 {"unit": "W/m²", "desc_ru": "Прямая радиация",          "open_meteo": "direct_radiation"},
    "direct_normal_irradiance":         {"unit": "W/m²", "desc_ru": "DNI",                      "open_meteo": "direct_normal_irradiance"},
    "diffuse_radiation":                {"unit": "W/m²", "desc_ru": "Диффузная радиация",       "open_meteo": "diffuse_radiation"},
    "global_tilted_irradiance":         {"unit": "W/m²", "desc_ru": "GTI (средняя)",            "open_meteo": "global_tilted_irradiance"},
    "global_tilted_irradiance_instant": {"unit": "W/m²", "desc_ru": "GTI (моментальная)",       "open_meteo": "global_tilted_irradiance_instant"},
    "sunshine_duration":                {"unit": "s",    "desc_ru": "Длительность солнечно-го", "open_meteo": "sunshine_duration"},

    # ─────────────―― Осадки ―――――――――――――――――――――
    "precipitation":            {"unit": "mm", "desc_ru": "Осадки суммарные", "open_meteo": "precipitation"},
    "rain":                     {"unit": "mm", "desc_ru": "Дождь",            "open_meteo": "rain"},
    "showers":                  {"unit": "mm", "desc_ru": "Ливни",            "open_meteo": "showers"},
    "snowfall":                 {"unit": "cm", "desc_ru": "Снегопад",         "open_meteo": "snowfall"},
    "precipitation_probability":{"unit": "%",  "desc_ru": "Вероятн. осадков", "open_meteo": "precipitation_probability"},
    "snow_depth":               {"unit": "m",  "desc_ru": "Высота снега",     "open_meteo": "snow_depth"},
    "snowfall_height":          {"unit": "m",  "desc_ru": "Уровень снега",    "open_meteo": "snowfall_height"},

    # ─────────────―― Прочее мгновенное ―――――――――――
    "freezing_level_height":      {"unit": "m",    "desc_ru": "Высота 0 °C",        "open_meteo": "freezing_level_height"},
    "visibility":                 {"unit": "m",    "desc_ru": "Видимость",          "open_meteo": "visibility"},
    "weather_code":               {"unit": "code", "desc_ru": "WMO код погоды",     "open_meteo": "weather_code"},
    "vapour_pressure_deficit":    {"unit": "kPa",  "desc_ru": "Дефицит VPD",        "open_meteo": "vapour_pressure_deficit"},
    "cape":                       {"unit": "J/kg", "desc_ru": "CAPE",               "open_meteo": "cape"},
    "evapotranspiration":         {"unit": "mm",   "desc_ru": "Эвапотранспирация",  "open_meteo": "evapotranspiration"},
    "et0_fao_evapotranspiration": {"unit": "mm",   "desc_ru": "ET₀ FAO",            "open_meteo": "et0_fao_evapotranspiration"},
    "lightning_potential":        {"unit": "J/kg", "desc_ru": "Потенциал молний",   "open_meteo": "lightning_potential"},
    "is_day":                     {"unit": None,   "desc_ru": "1 — день, 0 — ночь", "open_meteo": "is_day"},

    # ─────────────―― Почва ――――――――――――――――――――――
    "soil_temperature_0cm":     {"unit": "°C",    "desc_ru": "T почвы 0 см",    "open_meteo": "soil_temperature_0cm"},
    "soil_temperature_6cm":     {"unit": "°C",    "desc_ru": "T почвы 6 см",    "open_meteo": "soil_temperature_6cm"},
    "soil_temperature_18cm":    {"unit": "°C",    "desc_ru": "T почвы 18 см",   "open_meteo": "soil_temperature_18cm"},
    "soil_temperature_54cm":    {"unit": "°C",    "desc_ru": "T почвы 54 см",   "open_meteo": "soil_temperature_54cm"},
    "soil_moisture_0_to_1cm":   {"unit": "m³/m³", "desc_ru": "Влажн. 0-1 см",   "open_meteo": "soil_moisture_0_to_1cm"},
    "soil_moisture_1_to_3cm":   {"unit": "m³/m³", "desc_ru": "Влажн. 1-3 см",   "open_meteo": "soil_moisture_1_to_3cm"},
    "soil_moisture_3_to_9cm":   {"unit": "m³/m³", "desc_ru": "Влажн. 3-9 см",   "open_meteo": "soil_moisture_3_to_9cm"},
    "soil_moisture_9_to_27cm":  {"unit": "m³/m³", "desc_ru": "Влажн. 9-27 см",  "open_meteo": "soil_moisture_9_to_27cm"},
    "soil_moisture_27_to_81cm": {"unit": "m³/m³", "desc_ru": "Влажн. 27-81 см", "open_meteo": "soil_moisture_27_to_81cm"},

    # ─────────────―― Daily-агрегации (добавочные) ―――
    "temperature_max":                {"unit": "°C",    "desc_ru": "T макс/день",           "open_meteo": "temperature_2m_max"},
    "temperature_mean":               {"unit": "°C",    "desc_ru": "T сред/день",           "open_meteo": "temperature_2m_mean"},
    "temperature_min":                {"unit": "°C",    "desc_ru": "T мин/день",            "open_meteo": "temperature_2m_min"},
    "apparent_temperature_max":       {"unit": "°C",    "desc_ru": "Feels-like макс",       "open_meteo": "apparent_temperature_max"},
    "apparent_temperature_mean":      {"unit": "°C",    "desc_ru": "Feels-like сред",       "open_meteo": "apparent_temperature_mean"},
    "apparent_temperature_min":       {"unit": "°C",    "desc_ru": "Feels-like мин",        "open_meteo": "apparent_temperature_min"},
    "precipitation_sum":              {"unit": "mm",    "desc_ru": "Осадки/день",           "open_meteo": "precipitation_sum"},
    "rain_sum":                       {"unit": "mm",    "desc_ru": "Дождь/день",            "open_meteo": "rain_sum"},
    "showers_sum":                    {"unit": "mm",    "desc_ru": "Ливни/день",            "open_meteo": "showers_sum"},
    "snowfall_sum":                   {"unit": "cm",    "desc_ru": "Снег/день",             "open_meteo": "snowfall_sum"},
    "precipitation_hours":            {"unit": "h",     "desc_ru": "Часы с осадками",       "open_meteo": "precipitation_hours"},
    "precipitation_probability_max":  {"unit": "%",     "desc_ru": "P(осадки) макс",        "open_meteo": "precipitation_probability_max"},
    "precipitation_probability_mean": {"unit": "%",     "desc_ru": "P(осадки) сред",        "open_meteo": "precipitation_probability_mean"},
    "precipitation_probability_min":  {"unit": "%",     "desc_ru": "P(осадки) мин",         "open_meteo": "precipitation_probability_min"},
    "sunrise":                        {"unit": "iso",   "desc_ru": "Восход Солнца",         "open_meteo": "sunrise"},
    "sunset":                         {"unit": "iso",   "desc_ru": "Закат Солнца",          "open_meteo": "sunset"},
    "daylight_duration":              {"unit": "s",     "desc_ru": "Длительность дня",      "open_meteo": "daylight_duration"},
    "uv_index_max":                   {"unit": None,    "desc_ru": "UV-индекс макс",        "open_meteo": "uv_index_max"},
    "uv_index_clear_sky_max":         {"unit": None,    "desc_ru": "UV-индекс (clear-sky)", "open_meteo": "uv_index_clear_sky_max"},
    "wind_speed_10m_max":             {"unit": "m/s",   "desc_ru": "Ветер 10 м макс",       "open_meteo": "wind_speed_10m_max"},
    "wind_gusts_10m_max":             {"unit": "m/s",   "desc_ru": "Порывы 10 м макс",      "open_meteo": "wind_gusts_10m_max"},
    "wind_direction_10m_dominant":    {"unit": "°",     "desc_ru": "Доминир. направление",  "open_meteo": "wind_direction_10m_dominant"},
    "shortwave_radiation_sum":        {"unit": "MJ/m²", "desc_ru": "Сумма радиации",        "open_meteo": "shortwave_radiation_sum"},
    "et0_fao_evapotranspiration_sum": {"unit": "mm",    "desc_ru": "Сумма ET₀ FAO",         "open_meteo": "et0_fao_evapotranspiration"},

}
