import threading
from django.db import models

_thread_locals = threading.local()

def get_current_school():
    return getattr(_thread_locals, 'school', None)

def set_current_school(school):
    _thread_locals.school = school

class SchoolScopedManager(models.Manager):
    """
    Manager that automatically filters by the school of the currently logged-in user.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        school = get_current_school()
        if school:
            return qs.filter(school=school)
        return qs
