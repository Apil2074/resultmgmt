from django.urls import path
from .views_web import subject_list, subject_inline_edit, subject_spreadsheet_edit

urlpatterns = [
    path('', subject_list, name='subject_list'),
    path('spreadsheet-edit/', subject_spreadsheet_edit, name='subject_spreadsheet_edit'),
    path('<int:subject_id>/inline-edit/', subject_inline_edit, name='subject_inline_edit'),
]
