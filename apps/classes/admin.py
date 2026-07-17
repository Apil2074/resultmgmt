from django.contrib import admin
from .models import Class

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'section', 'school', 'session']
    list_filter = ['school', 'session']
    search_fields = ['name', 'section']
