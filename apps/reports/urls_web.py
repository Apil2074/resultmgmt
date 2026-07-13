from django.urls import path
from .views_web import (
    reports_index, 
    toppers_report, 
    merit_list, 
    pass_fail_report, 
    subject_analysis,
    exam_analytics
)

urlpatterns = [
    path('', reports_index, name='reports_index'),
    path('analytics/<int:exam_id>/', exam_analytics, name='exam_analytics'),
    path('toppers/<int:exam_id>/', toppers_report, name='toppers_report'),
    path('merit/<int:exam_id>/', merit_list, name='merit_list'),
    path('pass-fail/<int:exam_id>/', pass_fail_report, name='pass_fail_report'),
    path('subject/<int:exam_id>/<int:subject_id>/', subject_analysis, name='subject_analysis'),
]
