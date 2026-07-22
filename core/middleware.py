from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve, Resolver404
from core.thread_locals import set_current_school

class SchoolRequiredMiddleware:
    """
    Enforces that authenticated users must have a school assigned to their profile
    before they can access school-scoped resources (e.g. classes, sessions, exams, marks, reports).
    If they do not have a school assigned (like a floating Super Admin), they are redirected
    to the dashboard with a warning message.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                resolver_match = resolve(request.path_info)
                url_name = resolver_match.url_name
            except Resolver404:
                url_name = None

            # 1. Enforce subscription validity check for non-superadmin accounts
            if not request.user.is_super_admin and request.user.school:
                if not request.user.school.has_active_subscription():
                    exempt_sub_urls = ['logout', 'subscription_expired']
                    if url_name not in exempt_sub_urls:
                        return redirect('subscription_expired')

            # Skip checking for public/auth/dashboard paths and django admin / static files / REST APIs
            exempt_url_names = [
                'login', 'logout', 'change_password', 'profile', 'dashboard',
                'api_login', 'api_logout', 'api_change_password', 'api_me',
                'super_schools', 'create_school_and_admin', 'subscription_expired', 
                'edit_school', 'delete_school', 'reset_school_admin_password', 'forgot_password',
                'send_notification', 'send_teacher_notification', 'mark_notification_read', 'delete_notification',
                'super_notifications', 'super_subscriptions', 'super_analytics',
                'super_reports', 'super_settings',
                'super_ticket_list', 'super_ticket_detail'
            ]
            exempt_prefixes = ['/admin/', '/static/', '/media/', '/api/']

            is_exempt = False
            if url_name in exempt_url_names:
                is_exempt = True
            else:
                for prefix in exempt_prefixes:
                    if request.path_info.startswith(prefix):
                        is_exempt = True
                        break

            if not is_exempt and not getattr(request.user, 'school', None):
                messages.error(request, 'No school is assigned to your account. You must have an assigned school to manage this section.')
                return redirect('dashboard')
                
            if hasattr(request.user, 'school') and request.user.school:
                set_current_school(request.user.school)
            else:
                set_current_school(None)

        try:
            response = self.get_response(request)
        finally:
            set_current_school(None)
            
        return response
