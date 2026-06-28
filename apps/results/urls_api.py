from django.urls import path
from .views_api import ResultAPIView
urlpatterns = [path('ledger/<int:exam_id>/<int:class_id>/', ResultAPIView.as_view(), name='api_ledger'),]
