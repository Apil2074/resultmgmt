from django.urls import path
from .views_web import (
    school_profile, session_list, super_schools,
    create_school_and_admin, subscription_expired,
    edit_school, reset_school_admin_password, delete_school,
    super_notifications, super_subscriptions,
    super_analytics, super_reports, super_settings,
    super_ticket_list, super_ticket_detail, teacher_notifications
)

urlpatterns = [
    path('profile/', school_profile, name='school_profile'),
    path('sessions/', session_list, name='session_list'),
    path('', super_schools, name='super_schools'),
    path('create/', create_school_and_admin, name='create_school_and_admin'),
    path('edit/<int:school_id>/', edit_school, name='edit_school'),
    path('delete/<int:school_id>/', delete_school, name='delete_school'),
    path('reset-password/<int:school_id>/', reset_school_admin_password, name='reset_school_admin_password'),
    path('subscription-expired/', subscription_expired, name='subscription_expired'),
    path('notifications/', super_notifications, name='super_notifications'),
    path('teacher-notifications/', teacher_notifications, name='teacher_notifications'),
    path('subscriptions/', super_subscriptions, name='super_subscriptions'),
    path('analytics/', super_analytics, name='super_analytics'),
    path('reports/', super_reports, name='super_reports'),
    path('settings/', super_settings, name='super_settings'),
    path('support/', super_ticket_list, name='super_ticket_list'),
    path('support/<int:ticket_id>/', super_ticket_detail, name='super_ticket_detail'),
]
