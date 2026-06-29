"""
URL configuration for RMS project
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

# Override admin site permission check to restrict access exclusively to SUPER_ADMIN role
def custom_has_permission(request):
    return (
        request.user.is_active and 
        request.user.is_authenticated and 
        getattr(request.user, 'role', None) == 'SUPER_ADMIN'
    )

admin.site.has_permission = custom_has_permission

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Frontend views (HTML pages)
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
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
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# Trivial change to force reload
urlpatterns += []

# Custom error handlers
from django.views.generic.base import TemplateView
handler404 = TemplateView.as_view(template_name='404.html')
handler500 = TemplateView.as_view(template_name='500.html')
