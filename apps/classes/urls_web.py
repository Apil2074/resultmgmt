from django.urls import path
from django.urls import path
from .views_web import class_list, class_detail, bulk_map_subjects, class_spreadsheet_edit

urlpatterns = [
    path('', class_list, name='class_list'),
    path('<slug:slug>/', class_detail, name='class_detail'),
    path('<slug:slug>/bulk-map-subjects/', bulk_map_subjects, name='bulk_map_subjects'),
    path('<slug:slug>/spreadsheet-edit/', class_spreadsheet_edit, name='class_spreadsheet_edit'),
]
