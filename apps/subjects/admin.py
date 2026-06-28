from django.contrib import admin
from .models import Subject, SubjectMarkingStructure, StudentSubjectEnrollment

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'class_obj', 'school', 'credit_hour', 'subject_type', 'order']
    list_filter = ['school', 'class_obj', 'subject_type']
    search_fields = ['name', 'code']

@admin.register(SubjectMarkingStructure)
class SubjectMarkingStructureAdmin(admin.ModelAdmin):
    list_display = ['subject', 'has_theory', 'theory_full_marks', 'has_internal', 'internal_full_marks']

@admin.register(StudentSubjectEnrollment)
class StudentSubjectEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'enrolled_at']
