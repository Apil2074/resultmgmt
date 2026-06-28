"""Audit App — Web views"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import AuditLog


@login_required
def audit_log(request):
    school = request.user.school
    logs = AuditLog.objects.filter(school=school).select_related('user').order_by('-timestamp')[:200]
    return render(request, 'audit/log.html', {'logs': logs})
