from django.urls import path
from rest_framework.routers import DefaultRouter
from .views_api import SchoolViewSet, SessionViewSet
router = DefaultRouter()
router.register('', SchoolViewSet, basename='school')
router.register('sessions', SessionViewSet, basename='session')
urlpatterns = router.urls
