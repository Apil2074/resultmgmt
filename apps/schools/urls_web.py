from django.urls import path
from .views_web import dashboard, school_profile, session_list

urlpatterns = [
    path('', dashboard, name='dashboard'),
]
