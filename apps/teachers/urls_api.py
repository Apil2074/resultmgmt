from django.urls import path
from .views_api import TeacherDashboardAPIView

urlpatterns = [
    path('dashboard/', TeacherDashboardAPIView.as_view(), name='api_teacher_dashboard'),
]
