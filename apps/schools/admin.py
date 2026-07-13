from django.contrib import admin
from .models import School, AcademicSession

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'principal_name','establishment_year']
    search_fields = ['name', 'principal_name']
    

@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'is_active']
    list_filter = ['is_active', 'school']
    search_fields = ['name']
