"""
Accounts App — Web views (login, logout, change password, profile)
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from apps.audit.models import AuditLog


class LoginView(View):
    template_name = 'auth/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        user = authenticate(request, username=username, password=password)
        if user:
            if not user.is_active:
                messages.error(request, 'Your account is disabled.')
                return render(request, self.template_name)

            if user.school and not user.is_super_admin and not user.school.has_active_subscription():
                messages.error(request, 'Your school subscription has expired. Please contact the Super Admin.')
                return render(request, self.template_name)

            login(request, user)

            if not remember_me:
                request.session.set_expiry(0)

            # Log the login
            AuditLog.objects.create(
                school=user.school,
                user=user,
                action=AuditLog.Action.LOGIN,
                model_name='User',
                object_id=str(user.pk),
                object_repr=str(user),
                ip_address=self._get_ip(request),
            )
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
            return render(request, self.template_name, {'username': username})

    def _get_ip(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0] if xff else request.META.get('REMOTE_ADDR')


@login_required
def logout_view(request):
    AuditLog.objects.create(
        school=request.user.school,
        user=request.user,
        action=AuditLog.Action.LOGOUT,
        model_name='User',
        object_id=str(request.user.pk),
        object_repr=str(request.user),
    )
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


@method_decorator(login_required, name='dispatch')
class ChangePasswordView(View):
    template_name = 'auth/change_password.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not request.user.check_password(old_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, self.template_name)

        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return render(request, self.template_name)

        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, self.template_name)

        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Password changed successfully.')
        return redirect('dashboard')


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name).strip()
        user.last_name = request.POST.get('last_name', user.last_name).strip()
        user.email = request.POST.get('email', user.email).strip()
        user.phone = request.POST.get('phone', user.phone).strip()
        
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
            
        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
        
    return render(request, 'auth/profile.html', {'user': user})
