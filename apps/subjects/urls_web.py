from django.urls import path
from .views_web import subject_list
urlpatterns = [path('', subject_list, name='subject_list'),]
