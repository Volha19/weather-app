from django.urls import path
from . import views

urlpatterns = [
    path('', views.weather_dashboard, name='weather-home'),
    path('widgets/cards/add/', views.add_card, name='card-add'),
    path('widgets/weather/', views.weather_widget, name='weather-widget'),
    path('widgets/recent/', views.recent_widget, name='recent-widget'),
    path('widgets/stats/', views.stats_widget, name='stats-widget'),
    path('widgets/alerts/', views.alerts_widget, name='alerts-widget'),
    path('widgets/graph/', views.graph_widget, name='graph-widget'),
    path('widgets/map-tile/<str:layer>/<int:z>/<int:x>/<int:y>/', views.map_tile_proxy, name='map_tile_proxy'),
    path('widgets/map-tile/<str:layer>/<int:z>/<int:x>/<int:y>', views.map_tile_proxy, name='map_tile_proxy_no_slash'),
]