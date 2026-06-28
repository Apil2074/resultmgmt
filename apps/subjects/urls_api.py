from django.urls import path
from rest_framework.routers import DefaultRouter
from .views_api import SubjectViewSet
router = DefaultRouter()
router.register('', SubjectViewSet, basename='subject')
urlpatterns = router.urls
