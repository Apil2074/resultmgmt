from django.contrib import admin
from .models import Exam, ExamClass

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'session', 'start_date', 'end_date', 'status', 'is_locked']
    list_filter = ['school', 'session', 'status', 'is_locked']
    search_fields = ['name']

@admin.register(ExamClass)
class ExamClassAdmin(admin.ModelAdmin):
    list_display = ['exam', 'class_obj']
