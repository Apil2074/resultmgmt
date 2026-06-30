from django.urls import path
from .views_web import (
    school_profile, session_list, super_schools,
    create_school_and_admin, subscription_expired,
    edit_school, reset_school_admin_password,
)

urlpatterns = [
    path('profile/', school_profile, name='school_profile'),
    path('sessions/', session_list, name='session_list'),
    path('', super_schools, name='super_schools'),
    path('create/', create_school_and_admin, name='create_school_and_admin'),
    path('edit/<int:school_id>/', edit_school, name='edit_school'),
    path('reset-password/<int:school_id>/', reset_school_admin_password, name='reset_school_admin_password'),
    path('subscription-expired/', subscription_expired, name='subscription_expired'),
]
