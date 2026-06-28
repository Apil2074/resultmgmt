from django.urls import path
from rest_framework.routers import DefaultRouter
from .views_api import StudentViewSet
router = DefaultRouter()
router.register('', StudentViewSet, basename='student')
urlpatterns = router.urls
