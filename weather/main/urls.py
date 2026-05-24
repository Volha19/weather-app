from django.urls import path
from . import views

urlpatterns = [
    path('', views.hello_weather, name='weather-home'),
    path('widgets/cards/add/', views.add_card, name='card-add'),
    path('widgets/weather/', views.weather_widget, name='weather-widget'),
    path('widgets/recent/', views.recent_widget, name='recent-widget'),
    path('widgets/stats/', views.stats_widget, name='stats-widget'),
    path('widgets/graph/', views.graph_widget, name='graph-widget'),
]