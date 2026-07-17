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
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django_ratelimit.decorators import ratelimit

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

    @method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True))
    def post(self, request):
        # Rate limiting is now enforced by django-ratelimit.
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

        if request.POST.get('remove_profile_picture') == 'on':
            user.profile_picture = None
        elif 'profile_picture' in request.FILES:
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
        SAFE_SUCCESS_MSG = "If this email is registered, a password reset link has been sent to it."

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
            # Generate token and base64 encoded user ID
            token = default_token_generator.make_token(user_to_reset)
            uid = urlsafe_base64_encode(force_bytes(user_to_reset.pk))
            
            # Build absolute reset confirmation link
            scheme = 'https' if request.is_secure() else 'http'
            domain = request.get_host()
            reset_link = f"{scheme}://{domain}/auth/reset-password/confirm/{uid}/{token}/"

            subject = "Reset Your Password — Multi-School RMS"
            body = (
                f"Hello {user_to_reset.get_full_name() or user_to_reset.username},\n\n"
                f"A password reset request was received for your admin account "
                f"on Multi-School Result Management System.\n\n"
                f"Please click the secure link below to reset your password:\n"
                f"  {reset_link}\n\n"
                f"This link is valid for a limited time and can only be used once.\n"
                f"If you did not request this, please ignore this email; your password will remain unchanged.\n\n"
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


class ResetPasswordConfirmView(View):
    template_name = "auth/reset_password_confirm.html"

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.filter(pk=uid, is_active=True).first()
        except (TypeError, ValueError, OverflowError):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            return render(request, self.template_name, {"validlink": True})
        else:
            return render(request, self.template_name, {"validlink": False})

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.filter(pk=uid, is_active=True).first()
        except (TypeError, ValueError, OverflowError):
            user = None

        if user is None or not default_token_generator.check_token(user, token):
            messages.error(request, "This password reset link is invalid or has expired.")
            return redirect("login")

        new_password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, self.template_name, {"validlink": True})

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, self.template_name, {"validlink": True})

        # Set the new password and save
        user.set_password(new_password)
        user.save()
        
        # Log the audit action
        AuditLog.objects.create(
            action=AuditLog.Action.UPDATE,
            user=user,
            model_name="User",
            object_id=str(user.pk),
            object_repr=user.username,
            new_value={"action": "PASSWORD_RESET_VIA_TOKEN"},
            ip_address=get_trusted_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
        )

        messages.success(request, "Your password has been reset successfully. You can now log in.")
        return redirect("login")



class RegisterDemoView(View):
    template_name = 'auth/register_demo.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, self.template_name)

    def post(self, request):
        school_name = request.POST.get('school_name', '').strip()
        admin_name = request.POST.get('admin_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # Basic validation
        if not all([school_name, admin_name, email, phone, password, confirm_password]):
            messages.error(request, 'All fields are required.')
            return render(request, self.template_name, request.POST)

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, self.template_name, request.POST)
            
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, self.template_name, request.POST)

        # Check if email is already taken
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'This email is already registered.')
            return render(request, self.template_name, request.POST)

        try:
            from django.db import transaction
            from datetime import timedelta
            from django.utils import timezone
            
            with transaction.atomic():
                # Create School (1 day subscription)
                today = timezone.now().date()
                school = School.objects.create(
                    name=school_name,
                    email=email,
                    phone=phone,
                    address='Demo Address',
                    principal_name=admin_name,
                    subscription_start_date=today,
                    subscription_end_date=today + timedelta(days=1)
                )

                # Create Admin User
                first_name = admin_name.split()[0]
                last_name = ' '.join(admin_name.split()[1:]) if len(admin_name.split()) > 1 else ''
                
                # Use email as username if not provided
                base_username = email.split('@')[0]
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=User.Role.SCHOOL_ADMIN,
                    school=school,
                    phone=phone,
                    is_active=True
                )
                
                # Auto login
                user = authenticate(request, username=username, password=password)
                if user:
                    login(request, user)
                    AuditLog.objects.create(
                        school=user.school,
                        user=user,
                        action=AuditLog.Action.LOGIN,
                        model_name='User',
                        object_id=str(user.pk),
                        object_repr=str(user),
                        ip_address=get_trusted_client_ip(request),
                    )
                    messages.success(request, f'Welcome! Your 1-day demo for {school.name} is active.')
                    return redirect('dashboard')
                    
        except Exception as e:
            logger.exception("Error during demo registration: %s", e)
            messages.error(request, 'An error occurred during registration. Please try again.')
            return render(request, self.template_name, request.POST)
            
        return redirect('login')

class LandingPageView(View):
    template_name = "landing.html"

    def get(self, request):
        schools = School.objects.filter(is_active=True).exclude(logo='')
        return render(request, self.template_name, {"schools": schools})


@login_required
@require_POST
def send_notification(request):
    """View for Super Admin to send notifications to all School Admins."""
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Only Super Admins can send notifications.")
        return redirect('dashboard')
        
    title = request.POST.get('title', '').strip()
    message = request.POST.get('message', '').strip()
    
    if not title or not message:
        messages.error(request, "Both title and message are required.")
        return redirect('dashboard')
        
    from apps.accounts.models import Notification
    notification = Notification.objects.create(
        title=title,
        message=message,
        sender=request.user
    )
    
    # Get all school admins
    school_admins = User.objects.filter(role=User.Role.SCHOOL_ADMIN)
    notification.recipients.add(*school_admins)
    
    # Audit log
    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=request.user,
        model_name="Notification",
        object_id=str(notification.pk),
        object_repr=notification.title,
        new_value={"title": title},
        ip_address=get_trusted_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
    )
    
    messages.success(request, "Notification broadcast successfully to all School Admins!")
    return redirect('dashboard')


@login_required
@require_POST
def send_teacher_notification(request):
    """View for School Admin to send notifications to all Teachers in their school."""
    if not request.user.can_manage_school():
        messages.error(request, "Access denied. Only School Admins can send notifications.")
        return redirect('dashboard')
        
    title = request.POST.get('title', '').strip()
    message = request.POST.get('message', '').strip()
    
    if not title or not message:
        messages.error(request, "Both title and message are required.")
        return redirect('dashboard')
        
    from apps.accounts.models import Notification
    notification = Notification.objects.create(
        title=title,
        message=message,
        sender=request.user
    )
    
    # Get all active teachers in this school
    teachers = User.objects.filter(role=User.Role.TEACHER, school=request.user.school, is_active=True)
    notification.recipients.add(*teachers)
    
    # Audit log
    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        user=request.user,
        model_name="Notification",
        object_id=str(notification.pk),
        object_repr=notification.title,
        new_value={"title": title, "type": "teacher_notification"},
        ip_address=get_trusted_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
    )
    
    messages.success(request, "Notification broadcast successfully to all Teachers!")
    return redirect('teacher_notifications')



@login_required
@require_POST
def mark_notification_read(request, pk):
    """Mark a specific notification as read for the logged-in user."""
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from apps.accounts.models import Notification
    
    notification = get_object_or_404(Notification, pk=pk)
    
    # Ensure user is a recipient
    if request.user in notification.recipients.all():
        notification.read_by.add(request.user)
        return JsonResponse({"status": "success", "message": "Notification marked as read."})
        
    return JsonResponse({"status": "error", "message": "Not a recipient."}, status=403)


@login_required
@require_POST
def delete_notification(request, pk):
    """Delete a notification sent by the current user."""
    from django.shortcuts import get_object_or_404
    from apps.accounts.models import Notification
    
    notification = get_object_or_404(Notification, pk=pk)
    
    # Only the sender can delete their notification
    if notification.sender_id == request.user.id or request.user.is_super_admin:
        notification.delete()
        messages.success(request, "Notification deleted successfully.")
    else:
        messages.error(request, "You don't have permission to delete this notification.")
        
    # Redirect back to the referrer or dashboard
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))
