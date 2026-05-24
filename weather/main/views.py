from django.shortcuts import render
from django.db.models import Avg
from django.conf import settings
from .models import SearchHistory
import json
from uuid import uuid4
from .weather_service import WeatherService, WeatherServiceError


GRAPH_METRICS = [
    {'value': 'temperature', 'label': 'Temperature'},
    {'value': 'feels_like', 'label': 'Feels Like'},
    {'value': 'humidity', 'label': 'Humidity'},
    {'value': 'pressure', 'label': 'Pressure'},
    {'value': 'wind_speed', 'label': 'Wind Speed'},
]


CARD_TYPES = {
    'weather': {
        'title': 'Weather Widget',
        'span': 'span-8',
        'body_template': 'main/partials/cards/weather.html',
    },
    'stats': {
        'title': 'Today Snapshot',
        'span': 'span-4',
        'note': 'Auto-refresh every 20 seconds.',
        'body_template': 'main/partials/cards/stats.html',
    },
    'recent': {
        'title': 'Recent Searches',
        'span': 'span-6',
        'note': 'Latest requests from your database.',
        'body_template': 'main/partials/cards/recent.html',
    },
    'help': {
        'title': 'How To Use',
        'span': 'span-6',
        'steps': [
            'Enter a city and fetch weather.',
            'Watch recent and stats cards refresh.',
            'Keep this page open as your mini weather board.',
        ],
        'body_template': 'main/partials/cards/help.html',
    },
    'graph': {
        'title': 'Graph of Weather Data',
        'span': 'span-6',
        'body_template': 'main/partials/cards/graph.html',
    },
}


def build_card(card_type: str, instance_id: str):
    card_config = CARD_TYPES.get(card_type, CARD_TYPES['graph'])
    card = {
        'id': instance_id,
        'instance_id': instance_id,
        'type': card_type if card_type in CARD_TYPES else 'graph',
        'title': card_config['title'],
        'span': card_config['span'],
        'body_template': card_config['body_template'],
    }

    if 'note' in card_config:
        card['note'] = card_config['note']
    if 'steps' in card_config:
        card['steps'] = card_config['steps']

    return card


def build_card_types_for_picker():
    return [
        {'value': key, 'label': value['title']}
        for key, value in CARD_TYPES.items()
    ]


def build_cards_config():
    return [
        build_card('weather', 'weather-main'),
        build_card('stats', 'stats-main'),
        build_card('recent', 'recent-main'),
        build_card('help', 'help-main'),
        build_card('graph', 'graph-main'),
    ]


def fetch_weather_for_city(city):
    """Return tuple (weather_dict_or_none, error_or_none)."""
    service = WeatherService(settings.OPENWEATHER_API_KEY)
    try:
        weather_data = service.fetch_current_weather(city)
        weather = weather_data.to_dict()
        city_name = weather_data.city.split(',')[0]

        SearchHistory.objects.create(
            city_name=city_name,
            temperature=weather_data.temperature,
            humidity=weather_data.humidity,
            pressure=weather_data.pressure,
            description=weather_data.description
        )
        return weather, None
    except WeatherServiceError as exc:
        return None, str(exc)


def fetch_forecast_for_city(city, metric='temperature'):
    """Fetch 5-day forecast and extract daily max/min for selected metric."""
    service = WeatherService(settings.OPENWEATHER_API_KEY)
    try:
        forecast = service.fetch_forecast(city, metric)
        return forecast.to_dict(), None
    except WeatherServiceError as exc:
        return None, str(exc)


def hello_weather(request):
    weather = None
    error = None

    if request.method == "POST":
        city = request.POST.get('city', '').strip()
        weather, error = fetch_weather_for_city(city)

    recent_searches = SearchHistory.objects.order_by('-searched_at')[:6]
    stats = {
        'search_count': SearchHistory.objects.count(),
        'avg_temp': SearchHistory.objects.aggregate(avg=Avg('temperature'))['avg'],
        'latest_city': recent_searches[0].city_name if recent_searches else None,
    }

    return render(request, "main/index.html", {
        'weather': weather,
        'error': error,
        'recent_searches': recent_searches,
        'stats': stats,
        'cards': build_cards_config(),
        'graph_metrics': GRAPH_METRICS,
        'card_type_options': build_card_types_for_picker(),
    })


def add_card(request):
    card_type = request.GET.get('card_type', 'graph')
    if card_type not in CARD_TYPES:
        card_type = 'graph'

    instance_id = f"{card_type}-{uuid4().hex[:8]}"
    card = build_card(card_type, instance_id)

    return render(request, "main/partials/card_section.html", {
        'card': card,
        'graph_metrics': GRAPH_METRICS,
    })


def weather_widget(request):
    weather = None
    error = None

    if request.method == "POST":
        city = request.POST.get('city', '').strip()
        weather, error = fetch_weather_for_city(city)

    return render(request, "main/partials/weather_result.html", {
        'weather': weather,
        'error': error,
    })


def recent_widget(request):
    recent_searches = SearchHistory.objects.order_by('-searched_at')[:6]
    return render(request, "main/partials/cards/recent.html", {
        'card': build_card('recent', 'recent-widget'),
        'recent_searches': recent_searches,
    })


def stats_widget(request):
    recent_searches = SearchHistory.objects.order_by('-searched_at')[:1]
    stats = {
        'search_count': SearchHistory.objects.count(),
        'avg_temp': SearchHistory.objects.aggregate(avg=Avg('temperature'))['avg'],
        'latest_city': recent_searches[0].city_name if recent_searches else None,
    }
    return render(request, "main/partials/cards/stats.html", {
        'card': build_card('stats', 'stats-widget'),
        'stats': stats,
    })


def graph_widget(request):
    """Fetch 5-day forecast and return max/min values for selected metric."""
    forecast = None
    error = None
    metric = 'temperature'
    card_instance_id = request.POST.get('card_instance_id', 'graph-main')

    if request.method == "POST":
        city = request.POST.get('city', '').strip()
        metric = request.POST.get('metric', 'temperature').lower()
        forecast, error = fetch_forecast_for_city(city, metric)

    if forecast:
        forecast_labels_json = json.dumps(forecast['labels'])
        forecast_max_json = json.dumps(forecast['max_values'])
        forecast_min_json = json.dumps(forecast['min_values'])
        metric_label = forecast['metric_label']
        metric_unit = forecast['unit']
        helper_text = None
    else:
        forecast_labels_json = json.dumps(['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5'])
        forecast_max_json = json.dumps([12, 14, 15, 13, 16])
        forecast_min_json = json.dumps([7, 8, 9, 8, 10])
        metric_label = 'Temperature'
        metric_unit = '°C'
        helper_text = 'Enter a city and fetch the 5-day forecast to see max and min lines for the selected metric.'

    chart_data = {
        'forecast': forecast,
        'metric': metric,
        'error': error,
        'forecast_labels_json': forecast_labels_json,
        'forecast_max_json': forecast_max_json,
        'forecast_min_json': forecast_min_json,
        'metric_label': metric_label,
        'metric_unit': metric_unit,
        'helper_text': helper_text,
        'card_instance_id': card_instance_id,
    }

    chart_data['fragment_only'] = True
    return render(request, "main/partials/cards/graph.html", chart_data)
