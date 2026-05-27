from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path('', lambda request: redirect('weather-home')),
    path('admin/', admin.site.urls),
    path('weather/', include('main.urls')),
]
