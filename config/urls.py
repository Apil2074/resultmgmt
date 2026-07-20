"""
URL configuration for E-Natija project
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.views.static import serve
from django.views.generic.base import TemplateView
from apps.accounts.views_web import LandingPageView


# SECURITY: Instead of monkey-patching admin.site.has_permission, 
# we rely on the built-in is_staff/is_superuser flags on the User model.
# The User model's save/create methods should enforce that ONLY SUPER_ADMIN gets is_staff=True.

# REMOVED: trigger_migration endpoint was an unauthenticated HTTP route that allowed
# any visitor to run `manage.py migrate` against the live database.
# Run migrations via SSH/console: python manage.py migrate

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Frontend views (HTML pages)
    path('', LandingPageView.as_view(), name='landing'),
    path('auth/', include('apps.accounts.urls_web')),
    path('dashboard/', include('apps.schools.urls_web')),
    path('schools/', include('apps.schools.urls_web_schools')),
    path('classes/', include('apps.classes.urls_web')),
    path('students/', include('apps.students.urls_web')),
    path('subjects/', include('apps.subjects.urls_web')),
    path('teachers/', include('apps.teachers.urls')),
    path('exams/', include('apps.exams.urls_web')),
    path('marks/', include('apps.marks.urls_web')),
    path('results/', include('apps.results.urls_web')),
    path('reports/', include('apps.reports.urls_web')),
    path('audit/', include('apps.audit.urls_web')),

    # REST API
    path('api/v1/', include([
        path('auth/', include('apps.accounts.urls_api')),
        path('schools/', include('apps.schools.urls_api')),
        path('classes/', include('apps.classes.urls_api')),
        path('students/', include('apps.students.urls_api')),
        path('subjects/', include('apps.subjects.urls_api')),
        path('exams/', include('apps.exams.urls_api')),
        path('marks/', include('apps.marks.urls_api')),
        path('results/', include('apps.results.urls_api')),
        path('reports/', include('apps.reports.urls_api')),
    ])),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Force Django to serve media files in production for cPanel hosting
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

# Custom error handlers
handler404 = TemplateView.as_view(template_name='404.html')
handler500 = TemplateView.as_view(template_name='500.html')

