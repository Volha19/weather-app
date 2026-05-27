from django.contrib import admin

from .models import SearchHistory


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
	list_display = ('city_name', 'temperature', 'humidity', 'pressure', 'searched_at')
	list_filter = ('searched_at', 'city_name')
	search_fields = ('city_name', 'description')
	ordering = ('-searched_at',)

