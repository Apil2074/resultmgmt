from django.urls import path
from .views_web import LoginView, logout_view, ChangePasswordView, profile_view, ForgotPasswordView, ResetPasswordConfirmView, LandingPageView, send_notification, send_teacher_notification, mark_notification_read, delete_notification, RegisterDemoView

urlpatterns = [
    path('register/', RegisterDemoView.as_view(), name='register_demo'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('profile/', profile_view, name='profile'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/confirm/<str:uidb64>/<str:token>/', ResetPasswordConfirmView.as_view(), name='password_reset_confirm'),
    path('notifications/send/', send_notification, name='send_notification'),
    path('notifications/send-teacher/', send_teacher_notification, name='send_teacher_notification'),
    path('notifications/read/<int:pk>/', mark_notification_read, name='mark_notification_read'),
    path('notifications/delete/<int:pk>/', delete_notification, name='delete_notification'),
]
