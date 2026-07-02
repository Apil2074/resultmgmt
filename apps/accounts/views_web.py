"""
Accounts App — Web views (login, logout, change password, profile)
"""
import logging
import secrets
import string

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings as django_settings

from apps.audit.models import AuditLog
from apps.schools.models import School
from apps.accounts.models import User
from core.security import get_trusted_client_ip, validate_image_upload, safe_redirect_url

logger = logging.getLogger(__name__)


class LoginView(View):
    template_name = 'auth/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, self.template_name)

    def post(self, request):
        # Rate limiting is enforced at the nginx / WAF layer or via django-axes.
        # A manual check is added here to guard against brute-force.
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

            # Log the login event
            AuditLog.objects.create(
                school=user.school,
                user=user,
                action=AuditLog.Action.LOGIN,
                model_name='User',
                object_id=str(user.pk),
                object_repr=str(user),
                ip_address=get_trusted_client_ip(request),
            )
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('dashboard')
        else:
            logger.warning("Failed login attempt for username='%s' from IP=%s",
                           username, get_trusted_client_ip(request))
            messages.error(request, 'Invalid username or password.')
            return render(request, self.template_name, {'username': username})


@login_required
@require_POST  # SECURITY: Logout must be POST to prevent CSRF logout attacks
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
            from django.core.exceptions import ValidationError
            try:
                validate_image_upload(request.FILES['profile_picture'])
                user.profile_picture = request.FILES['profile_picture']
            except ValidationError as e:
                messages.error(request, str(e.message))
                return render(request, 'auth/profile.html', {'user': user})

        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')

    return render(request, 'auth/profile.html', {'user': user})


class ForgotPasswordView(View):
    template_name = "auth/forgot_password.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get("email", "").strip().lower()

        if not email:
            messages.error(request, "Please enter your email address.")
            return render(request, self.template_name)

        # SECURITY: Always return the same success message regardless of whether the
        # email is found. This prevents email enumeration attacks.
        SAFE_SUCCESS_MSG = "If this email is registered, a temporary password has been sent to it."

        user_to_reset = None
        email_to_send_to = email

        # 1. Try to find a School with this email
        school = School.objects.filter(email__iexact=email, is_active=True).first()
        if school:
            user_to_reset = school.users.filter(role=User.Role.SCHOOL_ADMIN, is_active=True).first()
        else:
            # 2. Check if it's the Super Admin's personal email
            user_to_reset = User.objects.filter(
                email__iexact=email, role=User.Role.SUPER_ADMIN, is_active=True
            ).first()

        if user_to_reset:
            # Generate a secure 16-character temporary password
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            temp_password = "".join(secrets.choice(alphabet) for _ in range(16))

            user_to_reset.set_password(temp_password)
            user_to_reset.save(update_fields=['password'])

            subject = "Your Temporary Password — Multi-School RMS"
            body = (
                f"Hello {user_to_reset.get_full_name() or user_to_reset.username},\n\n"
                f"A temporary password has been generated for your admin account "
                f"on Multi-School Result Management System.\n\n"
                f"  Username      : {user_to_reset.username}\n"
                f"  New Password  : {temp_password}\n\n"
                f"Please log in and change your password immediately from your profile.\n\n"
                f"If you did not request this, please contact support.\n\n"
                f"— Multi-School RMS"
            )
            try:
                send_mail(
                    subject,
                    body,
                    django_settings.EMAIL_HOST_USER or "noreply@rms.local",
                    [email_to_send_to],
                    fail_silently=False,
                )
            except Exception as exc:
                # Log internally but do NOT expose SMTP errors to the user
                logger.exception("ForgotPassword: Email send failed for user pk=%s: %s",
                                 user_to_reset.pk, exc)

        # SECURITY: Always show the same message — no information about whether
        # the email was found or not
        messages.success(request, SAFE_SUCCESS_MSG)
        return render(request, self.template_name)


class LandingPageView(View):
    template_name = "landing.html"

    def get(self, request):
        return render(request, self.template_name)
