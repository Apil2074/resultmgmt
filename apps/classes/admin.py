from django.contrib import admin
from .models import Class, ClassTeacher

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'section', 'school', 'session']
    list_filter = ['school', 'session']
    search_fields = ['name', 'section']

@admin.register(ClassTeacher)
class ClassTeacherAdmin(admin.ModelAdmin):
    list_display = ['name', 'class_obj', 'email', 'phone']
    search_fields = ['name', 'email', 'phone']
