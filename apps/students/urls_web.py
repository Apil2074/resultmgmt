from django.urls import path
from .views_web import (student_list, student_create, student_detail,
    student_edit, student_delete, student_import, student_export_excel, student_import_template, student_bulk_delete, student_inline_edit, student_edit_modal)

urlpatterns = [
    path('', student_list, name='student_list'),
    path('create/', student_create, name='student_create'),
    path('<int:pk>/', student_detail, name='student_detail'),
    path('<int:pk>/edit/', student_edit, name='student_edit'),
    path('<int:pk>/edit/modal/', student_edit_modal, name='student_edit_modal'),
    path('<int:pk>/inline-edit/', student_inline_edit, name='student_inline_edit'),
    path('<int:pk>/delete/', student_delete, name='student_delete'),
    path('import/', student_import, name='student_import'),
    path('export/', student_export_excel, name='student_export'),
    path('template/', student_import_template, name='student_template'),
    path('bulk-delete/', student_bulk_delete, name='student_bulk_delete'),
]
