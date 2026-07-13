import os
path = r"c:\Users\wwwap\Desktop\resultmgmt\apps\schools\views_web.py"

views_code = """
@login_required
def super_schools(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    schools = School.objects.all().order_by('-created_at')
    return render(request, 'schools/super_schools.html', {'schools': schools})

@login_required
def super_notifications(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    from apps.accounts.models import User
    school_admins = User.objects.filter(role=User.Role.SCHOOL_ADMIN, is_active=True)
    return render(request, 'schools/super_notifications.html', {'school_admins': school_admins})

@login_required
def super_subscriptions(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    return render(request, 'schools/super_subscriptions.html')

@login_required
def super_analytics(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    return render(request, 'schools/super_analytics.html')

@login_required
def super_reports(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    return render(request, 'schools/super_reports.html')

@login_required
def super_settings(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    return render(request, 'schools/super_settings.html')
"""

with open(path, "a", encoding="utf-8") as f:
    f.write(views_code)

