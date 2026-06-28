"""
Schools context processor — injects school/session into all templates
"""


def school_context(request):
    context = {}
    if request.user.is_authenticated and hasattr(request.user, 'school') and request.user.school:
        school = request.user.school
        context['school'] = school
        context['active_session'] = school.get_active_session()
        context['grading_system'] = school.grading_system
    return context
