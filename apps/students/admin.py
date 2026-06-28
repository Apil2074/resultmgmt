from django.contrib import admin
from .models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'roll_number', 'class_obj', 'school', 'registration_number', 'is_active']
    list_filter = ['school', 'class_obj', 'is_active', 'gender']
    search_fields = ['name', 'roll_number', 'registration_number', 'symbol_number']
