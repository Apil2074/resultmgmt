from django.urls import path
from . import views_web

urlpatterns = [
    path('', views_web.teacher_list, name='teacher_list'),
    path('spreadsheet-edit/', views_web.teacher_spreadsheet_edit, name='teacher_spreadsheet_edit'),
    path('<int:teacher_id>/inline-edit/', views_web.teacher_inline_edit, name='teacher_inline_edit'),
    path('create/', views_web.teacher_create, name='teacher_create'),
    path('<int:pk>/', views_web.teacher_detail, name='teacher_detail'),
    path('<int:pk>/subjects/', views_web.teacher_subject_map, name='teacher_subject_map'),
    path('<int:pk>/edit/', views_web.teacher_edit, name='teacher_edit'),
    path('<int:pk>/delete/', views_web.teacher_delete, name='teacher_delete'),
    path('<int:pk>/create-user/', views_web.teacher_create_user, name='teacher_create_user'),
    path('<int:pk>/reset-password/', views_web.teacher_reset_password, name='teacher_reset_password'),
    path('<int:pk>/send-password-reset/', views_web.teacher_send_password_reset, name='teacher_send_password_reset'),
    path('import/', views_web.teacher_import, name='teacher_import'),
    path('import/template/', views_web.teacher_import_template, name='teacher_import_template'),
    path('bulk-delete/', views_web.teacher_bulk_delete, name='teacher_bulk_delete'),
    path('dashboard/', views_web.teacher_dashboard, name='teacher_dashboard'),
]
