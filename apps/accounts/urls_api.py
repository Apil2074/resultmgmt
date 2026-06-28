from django.urls import path
from .views_api import (
    LoginAPIView, LogoutAPIView, ChangePasswordAPIView,
    MeAPIView, UserListCreateAPIView
)

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='api_login'),
    path('logout/', LogoutAPIView.as_view(), name='api_logout'),
    path('change-password/', ChangePasswordAPIView.as_view(), name='api_change_password'),
    path('me/', MeAPIView.as_view(), name='api_me'),
    path('users/', UserListCreateAPIView.as_view(), name='api_users'),
]
