from django.urls import path
from rest_framework.routers import DefaultRouter
from .views_api import ExamViewSet
router = DefaultRouter()
router.register('', ExamViewSet, basename='exam')
urlpatterns = router.urls
