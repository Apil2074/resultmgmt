from django.urls import path
from .views_web import LoginView, logout_view, ChangePasswordView, profile_view

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('profile/', profile_view, name='profile'),
]
