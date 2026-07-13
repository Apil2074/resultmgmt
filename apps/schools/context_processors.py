"""
Schools context processor — injects school/session into all templates
"""


def school_context(request):
    context = {}
    if request.user.is_authenticated:
        if hasattr(request.user, 'school') and request.user.school:
            school = request.user.school
            context['school'] = school
            context['active_session'] = school.get_active_session()
            
        # Inject notifications context
        from apps.accounts.models import Notification
        user_notifications = Notification.objects.filter(recipients=request.user)
        unread_notifications = user_notifications.exclude(read_by=request.user)
        context['user_notifications'] = user_notifications[:5]
        context['unread_notifications_count'] = unread_notifications.count()
        context['unread_notifications'] = unread_notifications
        
    return context
