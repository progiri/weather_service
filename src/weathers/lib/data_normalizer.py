from typing import Any, Callable, Dict, List

from .param_catalog import OPEN_METEO_PARAM_CATALOG

Converter = Callable[[Any], Any]


class DataNormalizer:
    """
    Нормализует сырой ответ разных погодных API к единому каноническому набору полей.

    >>> normalizer = DataNormalizer()
    >>> raw = {"temperature_2m": 23.1, "relative_humidity_2m": 40}
    >>> normalizer.normalize("open_meteo", raw)
    {'temperature': 23.1, 'relative_humidity': 40}
    """

    def __init__(
        self,
        mapping: Dict[str, Dict[str, str | None]] | None = None,
        converters: Dict[str, Converter] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        mapping
            Словарь «канон → {provider: source_key}».
            По умолчанию берётся глобальный WEATHER_PARAM_CATALOG.
        converters
            Необязательные функции для перерасчёта единиц,
            задаются по каноническому имени параметра.
        """
        self._mapping = mapping or OPEN_METEO_PARAM_CATALOG
        self._converters = converters or {}

    def normalize(self, provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Вернёт dict c каноническими ключами; параметры,
        которых нет у провайдера или в payload, опускаются.
        """
        provider = provider.lower()
        if not self._is_known_provider(provider):
            raise ValueError(f"Unknown provider '{provider}'")

        result: Dict[str, Any] = {}

        for canon_key, meta in self._mapping.items():
            src_key = meta.get(provider)
            if not src_key:
                continue
            if src_key not in payload:
                continue

            value = payload[src_key]
            result[canon_key] = self._maybe_convert(canon_key, value)

        return result

    def open_meteo_standardize(
        self,
        payload: Dict[str, Any],
        sections: tuple[str, ...] = ("hourly", "minutely_15", "daily"),
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Разворачивает массивы внутри указанных секций Open-Meteo в список объектов
        с единым ключом time.
        """
        standardized: Dict[str, List[Dict[str, Any]]] = {}

        for section in sections:
            block = payload.get(section)
            if not block:
                continue

            times = block.get("time")
            if times is None:
                raise ValueError(f"Section '{section}' has no 'time' array")

            param_names = [k for k in block.keys() if k != "time"]
            rows: List[Dict[str, Any]] = []

            for idx, ts in enumerate(times):
                row = {"time": ts}
                for name in param_names:
                    values = block.get(name, [])
                    if idx < len(values):
                        row[name] = values[idx]
                rows.append(self.normalize("open_meteo", row))

            standardized[section] = rows
        return standardized

    def _is_known_provider(self, provider: str) -> bool:
        """Проверка, встречается ли provider хотя бы в одном meta-словаре."""
        return any(provider in meta for meta in self._mapping.values())

    def _maybe_convert(self, canon_key: str, value: Any) -> Any:
        """Запускает конвертер единиц, если он зарегистрирован."""
        converter = self._converters.get(canon_key)
        return converter(value) if converter else value

