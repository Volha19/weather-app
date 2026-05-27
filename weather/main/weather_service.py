from collections import defaultdict
from dataclasses import asdict, dataclass
import re
from typing import Any, Callable
from datetime import datetime

import requests


class WeatherServiceError(Exception):
    pass

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
    detail_labels: list[str]
    detail_max_values: list[float]
    detail_min_values: list[float]
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
    ONECALL_URL = "https://api.openweathermap.org/data/2.5/onecall"
    UNITS = 'metric'
    ERROR_MESSAGES = {
        'empty_city_name': "Please enter a city name.",
        'invalid_city_name': "City name contains invalid characters.",
        'api_key_not_configured': "Weather API key is not configured on the server.",
        'network': "Network error. Please try again.",
        'invalid_json': "Weather service returned invalid JSON.",
        'fetch_failed': "Could not fetch weather data.",
        'invalid_response': "Weather service response is invalid.",
        'missing_weather_fields': "Weather data is missing expected fields.",
        'missing_forecast_fields': "Forecast data is missing expected fields.",
    }

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

    def __init__(self, 
                 api_key: str, 
                 timeout: int = 86400):
        self.api_key = api_key
        self.timeout = timeout

    def validate_city(self, 
                      city: str) -> str:
        cleaned_city = (city or '').strip()
        if not cleaned_city:
            raise WeatherServiceError(self.ERROR_MESSAGES['empty_city_name'])
        if not self.CITY_PATTERN.match(cleaned_city):
            raise WeatherServiceError(self.ERROR_MESSAGES['invalid_city_name'])
        return cleaned_city

    def validate_api_key(self):
        if not self.api_key:
            raise WeatherServiceError(self.ERROR_MESSAGES['api_key_not_configured'])

    def resolve_metric(self, 
                       metric: str) -> tuple[str, MetricDefinition]:
        normalized_metric = metric if metric in self.METRIC_CONFIG else self.DEFAULT_METRIC
        return normalized_metric, self.METRIC_CONFIG[normalized_metric]

    def metric_value(self, 
                     data: dict[str, Any], 
                     metric_key: str) -> float:
        return self.METRIC_CONFIG[metric_key].extractor(data)

    def request_params(self, 
                       city: str) -> dict[str, Any]:
        return {'q': city, 'appid': self.api_key, 'units': self.UNITS}

    def fetch_for_city(self, 
                       url: str, 
                       city: str) -> dict[str, Any]:
        return self.request_json(url, self.request_params(city))

    def forecast_date(self, 
                      item: dict[str, Any]) -> str:
        return item['dt_txt'].split()[0]

    def forecast_datetime(self,
                          item: dict[str, Any]) -> datetime:
        return datetime.strptime(item['dt_txt'], '%Y-%m-%d %H:%M:%S')

    def extract_city_country(self, 
                             location_data: dict[str, Any]) -> tuple[str, str]:
        return location_data['name'], location_data['country']

    def format_city_label(self, 
                          city_name: str, 
                          country: str) -> str:
        return f"{city_name}, {country}"

    def extract_current_weather_meta(self, 
                                     data: dict[str, Any]) -> tuple[str, str, str, str]:
        city_name = data['name']
        country = data['sys']['country']
        description = str(data['weather'][0]['description']).title()
        icon = str(data['weather'][0]['icon'])
        return city_name, country, description, icon

    def parse_current_weather_data(self, 
                                   data: dict[str, Any]) -> WeatherData:
        city_name, country, description, icon = self.extract_current_weather_meta(data)

        temperature = self.metric_value(data, self.TEMPERATURE_METRIC)
        humidity = int(self.metric_value(data, self.HUMIDITY_METRIC))
        pressure = int(self.metric_value(data, self.PRESSURE_METRIC))

        return WeatherData(
            city=self.format_city_label(city_name, country),
            temperature=temperature,
            humidity=humidity,
            pressure=pressure,
            description=description,
            icon=icon,
        )

    def group_forecast_by_six_hours(
        self,
        forecast_items: list[dict[str, Any]],
        metric: MetricDefinition,
    ) -> dict[str, list[float]]:
        grouped_values: dict[str, list[float]] = defaultdict(list)
        for item in forecast_items:
            forecast_dt = self.forecast_datetime(item)
            bucket_hour = (forecast_dt.hour // 6) * 6
            bucket_start = forecast_dt.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)
            grouped_values[bucket_start.strftime('%Y-%m-%d %H:%M')].append(metric.extractor(item))
        return grouped_values

    def group_forecast_by_day(
        self,
        forecast_items: list[dict[str, Any]],
        metric: MetricDefinition,
    ) -> dict[str, list[float]]:
        grouped_values: dict[str, list[float]] = defaultdict(list)
        for item in forecast_items:
            grouped_values[self.forecast_date(item)].append(metric.extractor(item))
        return grouped_values

    def build_six_hour_extremes(
        self,
        forecast_by_day: dict[str, list[float]],
        ) -> tuple[list[str], list[float], list[float]]:
        labels: list[str] = []
        max_values: list[float] = []
        min_values: list[float] = []

        for bucket_start in sorted(forecast_by_day):
            bucket_values = forecast_by_day[bucket_start]
            labels.append(bucket_start)
            max_values.append(round(max(bucket_values), 1))
            min_values.append(round(min(bucket_values), 1))

        return labels, max_values, min_values

    def build_daily_extremes(
        self,
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

    def request_json(self, 
                     url: str, 
                     params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            data = response.json()
        except requests.RequestException as exc:
            raise WeatherServiceError(self.ERROR_MESSAGES['network']) from exc
        except ValueError as exc:
            raise WeatherServiceError(self.ERROR_MESSAGES['invalid_json']) from exc

        if response.status_code != 200:
            message = data.get('message') if isinstance(data, dict) else None
            raise WeatherServiceError(message or self.ERROR_MESSAGES['fetch_failed'])

        if not isinstance(data, dict):
            raise WeatherServiceError(self.ERROR_MESSAGES['invalid_response'])

        return data

    def fetch_current_weather(self, 
                              city: str) -> WeatherData:
        self.validate_api_key()
        city = self.validate_city(city)
        data = self.fetch_for_city(self.CURRENT_WEATHER_URL, city)

        try:
            return self.parse_current_weather_data(data)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise WeatherServiceError(self.ERROR_MESSAGES['missing_weather_fields']) from exc

    def fetch_forecast(self, 
                       city: str, 
                       metric: str = 'temperature') -> ForecastData:
        self.validate_api_key()
        city = self.validate_city(city)

        metric, selected_metric = self.resolve_metric(metric)

        data = self.fetch_for_city(self.FORECAST_URL, city)

        forecast_items = data.get('list')
        if not isinstance(forecast_items, list) or not forecast_items:
            raise WeatherServiceError(self.ERROR_MESSAGES['missing_forecast_fields'])

        try:
            forecast_by_day = self.group_forecast_by_day(forecast_items, selected_metric)
            detail_forecast_by_day = self.group_forecast_by_six_hours(forecast_items, selected_metric)
            labels, max_values, min_values = self.build_daily_extremes(forecast_by_day)
            detail_labels, detail_max_values, detail_min_values = self.build_six_hour_extremes(detail_forecast_by_day)
            city_name, country = self.extract_city_country(data['city'])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise WeatherServiceError(self.ERROR_MESSAGES['missing_forecast_fields']) from exc

        return ForecastData(
            labels=labels,
            max_values=max_values,
            min_values=min_values,
            detail_labels=detail_labels,
            detail_max_values=detail_max_values,
            detail_min_values=detail_min_values,
            metric=metric,
            metric_label=selected_metric.label,
            unit=selected_metric.unit,
            city=self.format_city_label(city_name, country),
        )
