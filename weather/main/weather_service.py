from collections import defaultdict
from dataclasses import asdict, dataclass
import re
from typing import Any, Callable

import requests


class WeatherServiceError(Exception):
    """Raised for user-facing weather service failures."""


@dataclass
class WeatherData:
    city: str
    temperature: float
    humidity: int
    pressure: int
    description: str
    icon: str

    def to_dict(self):
        return asdict(self)


@dataclass
class ForecastData:
    labels: list[str]
    max_values: list[float]
    min_values: list[float]
    metric: str
    metric_label: str
    unit: str
    city: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class MetricDefinition:
    label: str
    unit: str
    extractor: Callable[[dict[str, Any]], float]


class WeatherService:
    CITY_PATTERN = re.compile(r"^[A-Za-z\s\-'.]{2,100}$")
    DEFAULT_METRIC = 'temperature'
    TEMPERATURE_METRIC = 'temperature'
    HUMIDITY_METRIC = 'humidity'
    PRESSURE_METRIC = 'pressure'
    CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
    FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
    UNITS = 'metric'
    ERROR_MISSING_WEATHER_FIELDS = "Weather data is missing expected fields."
    ERROR_MISSING_FORECAST_FIELDS = "Forecast data is missing expected fields."

    METRIC_CONFIG = {
        'temperature': MetricDefinition(
            label='Temperature',
            unit='°C',
            extractor=lambda item: float(item['main']['temp']),
        ),
        'feels_like': MetricDefinition(
            label='Feels Like',
            unit='°C',
            extractor=lambda item: float(item['main']['feels_like']),
        ),
        'humidity': MetricDefinition(
            label='Humidity',
            unit='%',
            extractor=lambda item: float(item['main']['humidity']),
        ),
        'pressure': MetricDefinition(
            label='Pressure',
            unit='hPa',
            extractor=lambda item: float(item['main']['pressure']),
        ),
        'wind_speed': MetricDefinition(
            label='Wind Speed',
            unit='m/s',
            extractor=lambda item: float(item['wind']['speed']),
        ),
    }

    def __init__(self, api_key: str, timeout: int = 86400):
        self.api_key = api_key
        self.timeout = timeout

    def _validate_city(self, city: str) -> str:
        cleaned_city = (city or '').strip()
        if not cleaned_city:
            raise WeatherServiceError("Please enter a city name.")
        if not self.CITY_PATTERN.match(cleaned_city):
            raise WeatherServiceError("City name contains invalid characters.")
        return cleaned_city

    def _validate_api_key(self):
        if not self.api_key:
            raise WeatherServiceError("Weather API key is not configured on the server.")

    def _resolve_metric(self, metric: str) -> tuple[str, MetricDefinition]:
        normalized_metric = metric if metric in self.METRIC_CONFIG else self.DEFAULT_METRIC
        return normalized_metric, self.METRIC_CONFIG[normalized_metric]

    def _metric_value(self, data: dict[str, Any], metric_key: str) -> float:
        return self.METRIC_CONFIG[metric_key].extractor(data)

    def _request_params(self, city: str) -> dict[str, Any]:
        return {'q': city, 'appid': self.api_key, 'units': self.UNITS}

    def _fetch_for_city(self, url: str, city: str) -> dict[str, Any]:
        return self._get(url, self._request_params(city))

    @staticmethod
    def _forecast_date(item: dict[str, Any]) -> str:
        return item['dt_txt'].split()[0]

    @staticmethod
    def _extract_city_country(location_data: dict[str, Any]) -> tuple[str, str]:
        return location_data['name'], location_data['country']

    @staticmethod
    def _format_city_label(city_name: str, country: str) -> str:
        return f"{city_name}, {country}"

    @staticmethod
    def _extract_current_weather_meta(data: dict[str, Any]) -> tuple[str, str, str, str]:
        city_name = data['name']
        country = data['sys']['country']
        description = str(data['weather'][0]['description']).title()
        icon = str(data['weather'][0]['icon'])
        return city_name, country, description, icon

    def _parse_current_weather_data(self, data: dict[str, Any]) -> WeatherData:
        city_name, country, description, icon = self._extract_current_weather_meta(data)

        temperature = self._metric_value(data, self.TEMPERATURE_METRIC)
        humidity = int(self._metric_value(data, self.HUMIDITY_METRIC))
        pressure = int(self._metric_value(data, self.PRESSURE_METRIC))

        return WeatherData(
            city=self._format_city_label(city_name, country),
            temperature=temperature,
            humidity=humidity,
            pressure=pressure,
            description=description,
            icon=icon,
        )

    def _group_forecast_by_day(
        self,
        forecast_items: list[dict[str, Any]],
        metric: MetricDefinition,
    ) -> dict[str, list[float]]:
        grouped_values: dict[str, list[float]] = defaultdict(list)
        for item in forecast_items:
            grouped_values[self._forecast_date(item)].append(metric.extractor(item))
        return grouped_values

    @staticmethod
    def _build_daily_extremes(
        forecast_by_day: dict[str, list[float]],
    ) -> tuple[list[str], list[float], list[float]]:
        labels: list[str] = []
        max_values: list[float] = []
        min_values: list[float] = []

        for date in sorted(forecast_by_day)[:5]:
            day_values = forecast_by_day[date]
            labels.append(date)
            max_values.append(round(max(day_values), 1))
            min_values.append(round(min(day_values), 1))

        return labels, max_values, min_values

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            data = response.json()
        except requests.RequestException as exc:
            raise WeatherServiceError("Network error. Please try again.") from exc
        except ValueError as exc:
            raise WeatherServiceError("Weather service returned invalid JSON.") from exc

        if response.status_code != 200:
            message = data.get('message') if isinstance(data, dict) else None
            raise WeatherServiceError(message or "Could not fetch weather data.")

        if not isinstance(data, dict):
            raise WeatherServiceError("Weather service response is invalid.")

        return data

    def fetch_current_weather(self, city: str) -> WeatherData:
        self._validate_api_key()
        city = self._validate_city(city)
        data = self._fetch_for_city(self.CURRENT_WEATHER_URL, city)

        try:
            return self._parse_current_weather_data(data)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise WeatherServiceError(self.ERROR_MISSING_WEATHER_FIELDS) from exc

    def fetch_forecast(self, city: str, metric: str = 'temperature') -> ForecastData:
        self._validate_api_key()
        city = self._validate_city(city)

        metric, selected_metric = self._resolve_metric(metric)

        data = self._fetch_for_city(self.FORECAST_URL, city)

        forecast_items = data.get('list')
        if not isinstance(forecast_items, list) or not forecast_items:
            raise WeatherServiceError(self.ERROR_MISSING_FORECAST_FIELDS)

        try:
            forecast_by_day = self._group_forecast_by_day(forecast_items, selected_metric)
            labels, max_values, min_values = self._build_daily_extremes(forecast_by_day)
            city_name, country = self._extract_city_country(data['city'])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise WeatherServiceError(self.ERROR_MISSING_FORECAST_FIELDS) from exc

        return ForecastData(
            labels=labels,
            max_values=max_values,
            min_values=min_values,
            metric=metric,
            metric_label=selected_metric.label,
            unit=selected_metric.unit,
            city=self._format_city_label(city_name, country),
        )