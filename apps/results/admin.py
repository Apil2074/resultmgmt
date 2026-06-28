from django.contrib import admin
from .models import SubjectResult, StudentResult, GradeScale, GradeScaleEntry

@admin.register(SubjectResult)
class SubjectResultAdmin(admin.ModelAdmin):
    list_display = ['mark_entry', 'grade_point', 'grade', 'gpa', 'is_pass']
    list_filter = ['is_pass']

@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'overall_gpa', 'final_grade', 'class_rank', 'is_pass']
    list_filter = ['exam', 'final_grade', 'is_pass']
    search_fields = ['student__name']

@admin.register(GradeScale)
class GradeScaleAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'grading_system']

@admin.register(GradeScaleEntry)
class GradeScaleEntryAdmin(admin.ModelAdmin):
    list_display = ['scale', 'min_percentage', 'max_percentage', 'grade', 'grade_point']
