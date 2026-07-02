"""
Core Mixins — School-scoped querysets for multi-tenancy
"""
from django.shortcuts import get_object_or_404


class SchoolScopedMixin:
    """
    Mixin for DRF ViewSets and Views.
    Automatically scopes querysets to the current user's school.
    Super Admins can optionally pass ?school=<id> to scope to a specific school.
    """

    def get_school(self):
        """Return the school for the current request."""
        user = self.request.user
        if user.is_super_admin:
            school_id = self.request.query_params.get('school') or \
                        self.request.data.get('school')
            if school_id:
                from apps.schools.models import School
                return get_object_or_404(School, pk=school_id)
            return None  # Super admin viewing all
        return user.school

    def get_queryset(self):
        """Override to scope queryset to current school."""
        qs = super().get_queryset()
        school = self.get_school()
        if school:
            qs = qs.filter(school=school)
        return qs

    def perform_create(self, serializer):
        """Auto-set school on create."""
        school = self.get_school()
        if school:
            serializer.save(school=school)
        else:
            serializer.save()


class SchoolContextMixin:
    """
    Mixin for Django template views (non-API).
    Injects school context into all views.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated and user.school:
            context['school'] = user.school
            context['active_session'] = user.school.get_active_session()
        return context


class AuditMixin:
    """Mixin that logs model changes to AuditLog."""

    def log_action(self, action, obj, previous_value=None, new_value=None):
        from apps.audit.models import AuditLog
        try:
            AuditLog.objects.create(
                school=self.request.user.school,
                user=self.request.user,
                action=action,
                model_name=obj.__class__.__name__,
                object_id=str(obj.pk),
                object_repr=str(obj),
                previous_value=previous_value,
                new_value=new_value,
                ip_address=self.get_client_ip(),
            )
        except Exception:
            pass  # Never crash on audit failure

    def get_client_ip(self):
        """
        Return the real client IP using the trusted-proxy-aware helper.
        Only trusts X-Forwarded-For when TRUSTED_PROXY_IPS is configured.
        """
        from core.security import get_trusted_client_ip
        return get_trusted_client_ip(self.request)
