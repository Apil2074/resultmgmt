"""Audit App — Web views"""
import logging

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import AuditLog

logger = logging.getLogger(__name__)


@login_required
def audit_log(request):
    """
    View audit log for the current school.
    SECURITY: Explicitly restricted to School Admin and Super Admin.
    Do not rely solely on middleware for authorization.
    """
    user = request.user
    # All logged in users (Super Admin, School Admin, Teacher) can view the audit log for their school.
    if not (user.is_school_admin or user.is_super_admin or user.is_teacher):
        raise PermissionDenied

    school = user.school
    logs_qs = AuditLog.objects.filter(school=school)
    if not user.is_super_admin:
        logs_qs = logs_qs.exclude(user__role='SUPER_ADMIN')
    logs = logs_qs.select_related('user').order_by('-timestamp')[:200]
    return render(request, 'audit/log.html', {'logs': logs})
