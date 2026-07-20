from django.urls import path
from .views_web import (
    reports_index, 
    toppers_report, 
    subject_analysis,
    exam_analytics,
    export_toppers_pdf,
    compare_analytics
)

urlpatterns = [
    path('', reports_index, name='reports_index'),
    path('analytics/<int:exam_id>/', exam_analytics, name='exam_analytics'),
    path('compare/', compare_analytics, name='compare_analytics'),
    path('toppers/<int:exam_id>/', toppers_report, name='toppers_report'),
    path('toppers/<int:exam_id>/pdf/', export_toppers_pdf, name='export_toppers_pdf'),
    path('subject/<int:exam_id>/<int:subject_id>/', subject_analysis, name='subject_analysis'),
]
