"""
Accounts App — Custom User Model with Role-Based Access Control
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver


class User(AbstractUser):
    """Extended user model with role-based access."""

    class Role(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', _('Super Admin')
        SCHOOL_ADMIN = 'SCHOOL_ADMIN', _('School Admin')
        TEACHER = 'TEACHER', _('Teacher')

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.SCHOOL_ADMIN,
    )
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def save(self, *args, **kwargs):
        if self.role == self.Role.SUPER_ADMIN:
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_staff = False
            self.is_superuser = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_school_admin(self):
        return self.role == self.Role.SCHOOL_ADMIN

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    def can_edit_marks(self):
        return self.role in [self.Role.SUPER_ADMIN, self.Role.SCHOOL_ADMIN, self.Role.TEACHER]

    def can_publish_results(self):
        return self.role in [self.Role.SUPER_ADMIN, self.Role.SCHOOL_ADMIN]

    def can_manage_school(self):
        return self.role in [self.Role.SUPER_ADMIN, self.Role.SCHOOL_ADMIN]


class Notification(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_notifications'
    )
    recipients = models.ManyToManyField(
        User, related_name='received_notifications', blank=True
    )
    read_by = models.ManyToManyField(
        User, related_name='read_notifications', blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# Device Tokens for Push Notifications
# ---------------------------------------------------------------------------
class UserDeviceToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Device Token'
        verbose_name_plural = 'User Device Tokens'

    def __str__(self):
        return f"{self.user.username} - {self.token[:10]}..."


# ---------------------------------------------------------------------------
# File cleanup signals — delete old images when replaced or record deleted
# ---------------------------------------------------------------------------
from core.signals import delete_old_image_on_change, delete_image_on_delete

@receiver(pre_save, sender=User)
def user_profile_picture_cleanup(sender, instance, **kwargs):
    """Delete the old profile picture from storage when a new one is uploaded."""
    delete_old_image_on_change(instance, 'profile_picture')

@receiver(post_delete, sender=User)
def user_profile_picture_delete(sender, instance, **kwargs):
    """Delete the profile picture file when a user account is fully deleted."""
    delete_image_on_delete(instance, 'profile_picture')
