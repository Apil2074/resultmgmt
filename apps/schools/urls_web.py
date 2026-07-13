from django.urls import path
from .views_web import (
    dashboard, school_profile, session_list,
    support_ticket_list, support_ticket_detail
)

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('support/', support_ticket_list, name='support_ticket_list'),
    path('support/<int:ticket_id>/', support_ticket_detail, name='support_ticket_detail'),
]
