"""
Accounts App ΓÇö Web views (login, logout, change password, profile)
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

        # Check if the email belongs to any active user (Admin or Teacher)
        user_to_reset = User.objects.filter(
            email__iexact=email,
            role__in=[User.Role.SCHOOL_ADMIN, User.Role.SUPER_ADMIN, User.Role.TEACHER],
            is_active=True
        ).first()

        if not user_to_reset:
            # Fallback for Teachers: Check if there is an active Teacher with this email
            # where the User account might not exist or the email is out of sync.
            from apps.teachers.models import Teacher
            import secrets
            teacher = Teacher.objects.filter(email__iexact=email, is_active=True).first()
            if teacher:
                if not teacher.user:
                    # Auto-create user account for this teacher
                    username_base = teacher.email.split('@')[0]
                    user_to_reset = User.objects.create_user(
                        username=f"{username_base}_{teacher.pk}_{secrets.token_hex(2)}",
                        email=teacher.email,
                        password=secrets.token_urlsafe(16),
                        first_name=teacher.name,
                        role=User.Role.TEACHER,
                        school=teacher.school
                    )
                    teacher.user = user_to_reset
                    teacher.save()
                else:
                    # They have a user account, but the email was out of sync
                    user_to_reset = teacher.user
                    user_to_reset.email = email
                    user_to_reset.save()
            else:
                messages.error(request, "This email address is not registered in our system.")
                return render(request, self.template_name)

        # Generate token and base64 encoded user ID
        token = default_token_generator.make_token(user_to_reset)
        uid = urlsafe_base64_encode(force_bytes(user_to_reset.pk))
        
        # Build absolute reset confirmation link
        scheme = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
        reset_link = f"{scheme}://{domain}/auth/reset-password/confirm/{uid}/{token}/"

        subject = "Reset Your Password - E-Natija"
        
        html_message = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); padding: 30px 20px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px; letter-spacing: 1px;">E-Natija</h1>
                <p style="color: #e0e7ff; margin: 8px 0 0 0; font-size: 15px; font-weight: 500;">Result Management Software</p>
            </div>
            <div style="padding: 35px 30px; background-color: #ffffff;">
                <h3 style="color: #1f2937; margin-top: 0; font-size: 20px;">Hello {user_to_reset.get_full_name() or user_to_reset.username},</h3>
                <p style="color: #4b5563; line-height: 1.6; font-size: 16px;">
                    We received a request to reset the password for your account on <strong>E-Natija</strong>.
                </p>
                <p style="color: #4b5563; line-height: 1.6; font-size: 16px;">
                    Please click the secure button below to choose a new password:
                </p>
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{reset_link}" style="background-color: #4f46e5; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px; display: inline-block;">Reset My Password</a>
                </div>
                <p style="color: #6b7280; font-size: 14px; line-height: 1.5; margin-bottom: 0;">
                    <em>This link is valid for a limited time and can only be used once.</em><br><br>
                    If you did not request a password reset, you can safely ignore this email; your password will remain unchanged.
                </p>
            </div>
            <div style="background-color: #f8fafc; padding: 20px; text-align: center; color: #94a3b8; font-size: 13px; border-top: 1px solid #f1f5f9;">
                &copy; E-Natija. All rights reserved.
            </div>
        </div>
        """
        
        from django.utils.html import strip_tags
        plain_message = strip_tags(html_message.replace('<br>', '\n').replace('</div>', '\n').replace('</p>', '\n\n'))

        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=django_settings.EMAIL_HOST_USER or "noreply@rms.local",
                recipient_list=[user_to_reset.email],
                fail_silently=False,
                html_message=html_message
            )
        except Exception as exc:
            # Log internally but do NOT expose SMTP errors to the user
            logger.exception("ForgotPassword: Email send failed for user pk=%s: %s",
                             user_to_reset.pk, exc)

        messages.success(request, "A password reset link has been sent to your email address.")
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
                    subscription_end_date=today + timedelta(days=1),
                    is_demo=True
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
                    is_active=False
                )
                
                from django.contrib.auth.tokens import default_token_generator
                from django.utils.http import urlsafe_base64_encode
                from django.utils.encoding import force_bytes
                from django.core.mail import send_mail
                from django.conf import settings as django_settings

                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                scheme = 'https' if request.is_secure() else 'http'
                domain = request.get_host()
                activation_link = f"{scheme}://{domain}/auth/activate-demo/{uid}/{token}/"
                
                # Send activation email (HTML)
                from core.email_utils import demo_activation_email, superadmin_new_demo_email
                _subj, _plain, _html = demo_activation_email(user.first_name, activation_link)
                send_mail(
                    subject=_subj,
                    message=_plain,
                    from_email=getattr(django_settings, 'EMAIL_HOST_USER', 'noreply@rms.local'),
                    recipient_list=[user.email],
                    fail_silently=True,
                    html_message=_html,
                )
                
                # Notify superadmins (HTML)
                superadmins = User.objects.filter(role=User.Role.SUPER_ADMIN, is_active=True).values_list('email', flat=True)
                if superadmins:
                    _subj2, _plain2, _html2 = superadmin_new_demo_email(
                        school.name, user.get_full_name(), user.email, user.phone or '—'
                    )
                    send_mail(
                        subject=_subj2,
                        message=_plain2,
                        from_email=getattr(django_settings, 'EMAIL_HOST_USER', 'noreply@rms.local'),
                        recipient_list=list(superadmins),
                        fail_silently=True,
                        html_message=_html2,
                    )

                messages.success(request, 'Your demo account has been created. Please check your email for the activation link.')
                return redirect('login')
                    
        except Exception as e:
            logger.exception("Error during demo registration: %s", e)
            messages.error(request, 'An error occurred during registration. Please try again.')
            return render(request, self.template_name, request.POST)
            
        return redirect('login')

class LandingPageView(View):
    template_name = "landing.html"

    def get(self, request):
        schools = School.objects.filter(is_active=True).exclude(logo__isnull=True).exclude(logo='')
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


class DemoActivationView(View):
    def get(self, request, uidb64, token):
        from django.utils.http import urlsafe_base64_decode
        from django.utils.encoding import force_str
        from django.contrib.auth.tokens import default_token_generator
        from django.utils import timezone

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            # SECURITY FIX: Only match accounts that are currently inactive.
            # Filtering by is_active=False means:
            #   - Already-active accounts cannot be affected by replayed links.
            #   - Admin-disabled accounts (set to inactive after activation) cannot
            #     be re-activated by a user replaying their original activation email.
            user = User.objects.filter(pk=uid, is_active=False).first()
        except (TypeError, ValueError, OverflowError):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            user.is_active = True
            # SECURITY FIX: Burn the token by updating last_login.
            # Django's token generator includes last_login in its HMAC signature,
            # so updating it here invalidates this token immediately after first use,
            # making the activation link strictly one-time-use.
            user.last_login = timezone.now()
            user.save(update_fields=['is_active', 'last_login'])
            messages.success(request, "Your demo account is now activated! You can log in.")
            return redirect('login')
        else:
            messages.error(request, "The activation link is invalid or has expired.")
            return redirect('login')
