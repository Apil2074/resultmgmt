from django.contrib import admin
from .models import Subject, StudentSubjectEnrollment

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'class_obj', 'school', 'credit_hour', 'subject_type', 'order']
    list_filter = ['school', 'class_obj', 'subject_type']
    search_fields = ['name', 'code']

@admin.register(StudentSubjectEnrollment)
class StudentSubjectEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'enrolled_at']
