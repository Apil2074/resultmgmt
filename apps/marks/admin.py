from django.contrib import admin
from .models import MarkEntry

@admin.register(MarkEntry)
class MarkEntryAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'exam', 'theory_obtained', 'internal_obtained', 'special_value', 'school']
    list_filter = ['school', 'exam', 'special_value']
    search_fields = ['student__name', 'subject__name']
