from django.urls import path
from .views_api import MarkEntryAPIView
urlpatterns = [path('entry/<int:exam_id>/<int:class_id>/', MarkEntryAPIView.as_view(), name='api_mark_entry'),]
