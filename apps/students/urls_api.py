from django.urls import path
from rest_framework.routers import DefaultRouter
from .views_api import StudentViewSet, RegisterParentFCMTokenAPIView
router = DefaultRouter()
router.register('', StudentViewSet, basename='student')

urlpatterns = [
    path('register-parent-fcm-token/', RegisterParentFCMTokenAPIView.as_view(), name='api_register_parent_fcm_token'),
] + router.urls
