from django.urls import path
from .views_web import mark_entry, save_mark, save_marks_bulk, bulk_mark_import, mark_entry_template, save_full_marks, mark_entry_select, toggle_class_lock
urlpatterns = [
    path('entry/select/', mark_entry_select, name='mark_entry_select'),
    path('entry/<int:exam_id>/<int:class_id>/', mark_entry, name='mark_entry'), 
    path('save/', save_mark, name='save_mark'), 
    path('save-bulk/', save_marks_bulk, name='save_marks_bulk'), 
    path('save-full-marks/', save_full_marks, name='save_full_marks'), 
    path('bulk/<int:exam_id>/<int:class_id>/', bulk_mark_import, name='bulk_mark_import'), 
    path('template/<int:exam_id>/<int:class_id>/', mark_entry_template, name='mark_entry_template'),
    path('toggle-lock/<int:exam_id>/<int:class_id>/', toggle_class_lock, name='toggle_class_lock'),
]
