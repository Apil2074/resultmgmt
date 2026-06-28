from django.urls import path
from .views_web import class_list, class_detail

urlpatterns = [
    path('', class_list, name='class_list'),
    path('<slug:slug>/', class_detail, name='class_detail'),
]
