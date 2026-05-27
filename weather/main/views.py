from django.shortcuts import render
from django.db.models import Count
from django.conf import settings
from django.http import HttpResponse, HttpResponseServerError, StreamingHttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page
from .models import SearchHistory
import json
from uuid import uuid4
from .weather_service import WeatherService, WeatherServiceError
from .alerts_service import AlertsService, AlertsServiceError
import requests


GRAPH_METRICS = [
    {'value': 'temperature', 'label': 'Temperature'},
    {'value': 'feels_like', 'label': 'Feels Like'},
    {'value': 'humidity', 'label': 'Humidity'},
    {'value': 'pressure', 'label': 'Pressure'},
    {'value': 'wind_speed', 'label': 'Wind Speed'},
]


CARD_TYPES = {
    'weather': {
        'title': 'Current Weather',
        'span': 'span-6',
        'body_template': 'main/partials/cards/weather.html',
    },
    'map': {
        'title': 'Weather Map',
        'span': 'span-12',
        'body_template': 'main/partials/cards/weather.html',
    },
    'alerts': {
        'title': 'Alerts (Europe/CIS)',
        'span': 'span-6',
        'note': 'Free disaster alerts feed for Europe and CIS countries.',
        'body_template': 'main/partials/cards/alerts.html',
    },
    'stats': {
        'title': 'Today at a Glance',
        'span': 'span-6',
        'note': 'Updates after each search.',
        'body_template': 'main/partials/cards/stats.html',
    },
    'recent': {
        'title': 'Recent Cities',
        'span': 'span-6',
        'note': 'Refreshes after each successful search.',
        'body_template': 'main/partials/cards/recent.html',
    },
    'help': {
        'title': 'Quick Tips',
        'span': 'span-6',
        'steps': [
            'Type a city and get the latest weather.',
            'Recent cities update after a successful search.',
            'Keep this dashboard open for a quick weather check.',
        ],
        'body_template': 'main/partials/cards/help.html',
    },
    'graph': {
        'title': 'Weather Trends',
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


def build_stats_context():
    recent_searches = SearchHistory.objects.order_by('-searched_at')
    most_common_city = (
        SearchHistory.objects.values('city_name')
        .annotate(total=Count('id'))
        .order_by('-total', 'city_name')
        .first()
    )

    return {
        'search_count': SearchHistory.objects.count(),
        'most_common_city': most_common_city['city_name'] if most_common_city else None,
        'most_common_city_count': most_common_city['total'] if most_common_city else 0,
        'unique_city_count': SearchHistory.objects.values('city_name').distinct().count(),
        'latest_city': recent_searches[0].city_name if recent_searches else None,
        'latest_search_time': recent_searches[0].searched_at if recent_searches else None,
    }


def build_cards_config():
    return [
        build_card('weather', 'weather-main'),
        build_card('map', 'map-main'),
        build_card('alerts', 'alerts-main'),
        build_card('stats', 'stats-main'),
        build_card('recent', 'recent-main'),
        build_card('help', 'help-main'),
        build_card('graph', 'graph-main'),
    ]


def fetch_weather_for_city(city):
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
    service = WeatherService(settings.OPENWEATHER_API_KEY)
    try:
        forecast = service.fetch_forecast(city, metric)
        return forecast.to_dict(), None
    except WeatherServiceError as exc:
        return None, str(exc)


def build_5_day_graph_context(forecast, error, card_instance_id):
    if forecast:
        return {
            'forecast': forecast,
            'metric': forecast['metric'],
            'error': error,
            'forecast_labels_json': json.dumps(forecast['labels']),
            'forecast_max_json': json.dumps(forecast['max_values']),
            'forecast_min_json': json.dumps(forecast['min_values']),
            'forecast_detail_labels_json': json.dumps(forecast['detail_labels']),
            'forecast_detail_max_json': json.dumps(forecast['detail_max_values']),
            'forecast_detail_min_json': json.dumps(forecast['detail_min_values']),
            'metric_label': forecast['metric_label'],
            'metric_unit': forecast['unit'],
            'helper_text': 'This chart shows daily or 6-hour weather trends depending on the card size.',
            'card_instance_id': card_instance_id,
        }

    return {
        'forecast': None,
        'metric': 'temperature',
        'error': error,
        'forecast_labels_json': json.dumps(['00:00', '06:00', '12:00', '18:00']),
        'forecast_max_json': json.dumps([0, 0, 0, 0]),
        'forecast_min_json': json.dumps([0, 0, 0, 0]),
        'forecast_detail_labels_json': json.dumps(['2026-05-25 00:00', '2026-05-25 06:00', '2026-05-25 12:00', '2026-05-25 18:00']),
        'forecast_detail_max_json': json.dumps([0, 0, 0, 0]),
        'forecast_detail_min_json': json.dumps([0, 0, 0, 0]),
        'metric_label': 'Temperature',
        'metric_unit': '°C',
            'helper_text': 'This chart adapts to the card size and shows daily or 6-hour weather trends.',
        'card_instance_id': card_instance_id,
    }


def weather_dashboard(request):
    weather = None
    error = None

    if request.method == "POST":
        city = request.POST.get('city', '').strip()
        weather, error = fetch_weather_for_city(city)

    recent_searches = SearchHistory.objects.order_by('-searched_at')[:6]
    stats = build_stats_context()

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

    response = render(request, "main/partials/weather_result.html", {
        'weather': weather,
        'error': error,
    })

    if weather is not None and not error:
        response.headers['HX-Trigger'] = 'recent-updated, stats-updated'

    return response


def recent_widget(request):
    recent_searches = SearchHistory.objects.order_by('-searched_at')[:6]
    return render(request, "main/partials/cards/recent.html", {
        'card': build_card('recent', 'recent-widget'),
        'recent_searches': recent_searches,
    })


def stats_widget(request):
    stats = build_stats_context()
    return render(request, "main/partials/cards/stats.html", {
        'card': build_card('stats', 'stats-widget'),
        'stats': stats,
    })


def alerts_widget(request):
    service = AlertsService()
    alerts = []
    error = None

    try:
        alerts = [item.to_dict() for item in service.fetch_alerts(limit=8)]
    except AlertsServiceError as exc:
        error = str(exc)

    return render(request, "main/partials/cards/alerts.html", {
        'card': build_card('alerts', 'alerts-widget'),
        'alerts': alerts,
        'error': error,
    })


@require_GET
@cache_page(60 * 5)
def map_tile_proxy(request, layer, z, x, y):
    """Proxy OpenWeather map tiles so API key stays on the server.

    URL pattern: /widgets/map-tile/<layer>/<z>/<x>/<y>/?date=<unix>
    """
    api_key = settings.OPENWEATHER_API_KEY
    date = request.GET.get('date')
    base = f'https://maps.openweathermap.org/maps/2.0/weather/{layer}/{z}/{x}/{y}?appid={api_key}&opacity=0.65&fill_bound=true'
    url = base + ('&date=' + date if date else '')

    try:
        resp = requests.get(url, stream=True, timeout=15)
    except requests.RequestException:
        return HttpResponseServerError()

    if resp.status_code != 200:
        return HttpResponse(status=resp.status_code)

    content_type = resp.headers.get('Content-Type', 'image/png')
    streaming = StreamingHttpResponse(resp.iter_content(chunk_size=8192), content_type=content_type)
    streaming['Cache-Control'] = 'public, max-age=300'
    if resp.headers.get('Content-Length'):
        streaming['Content-Length'] = resp.headers.get('Content-Length')

    return streaming


def graph_widget(request):
    forecast = None
    error = None
    metric = 'temperature'
    card_instance_id = request.POST.get('card_instance_id', 'graph-main')

    if request.method == "POST":
        city = request.POST.get('city', '').strip()
        metric = request.POST.get('metric', 'temperature').lower()
        forecast, error = fetch_forecast_for_city(city, metric)

    chart_data = build_5_day_graph_context(forecast, error, card_instance_id)

    chart_data['fragment_only'] = True
    return render(request, "main/partials/cards/graph.html", chart_data)


