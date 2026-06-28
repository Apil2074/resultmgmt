from django.urls import path
from rest_framework.routers import DefaultRouter
from .views_api import ClassViewSet
router = DefaultRouter()
router.register('', ClassViewSet, basename='class')
urlpatterns = router.urls
