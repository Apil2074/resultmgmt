"""
Schools App � School Profile and Academic Session models
"""
from django.db import models
from django.utils import timezone
from django.conf import settings

class School(models.Model):
    """Top-level tenant � all data is scoped to a school."""



    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='school_logos/', null=True, blank=True)
    dashboard_background = models.ImageField(upload_to='school_backgrounds/', null=True, blank=True)
    dashboard_background_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.10, help_text="Opacity of the background image (0.00 to 1.00)")
    address = models.TextField()
    phone = models.CharField(max_length=30)
    email = models.EmailField()
    website = models.URLField(blank=True)
    establishment_year = models.PositiveIntegerField(null=True, blank=True)
    principal_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    subscription_start_date = models.DateField(null=True, blank=True)
    subscription_end_date = models.DateField(null=True, blank=True)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'School'
        verbose_name_plural = 'Schools'

    def __str__(self):
        return self.name

    def has_active_subscription(self):
        from django.utils import timezone
        now = timezone.now().date()
        if self.subscription_start_date and self.subscription_start_date > now:
            return False
        if self.subscription_end_date and self.subscription_end_date < now:
            return False
        return True

    def get_active_session(self):
        return self.academic_sessions.filter(is_active=True).first()


class AcademicSession(models.Model):
    """Academic year / session (e.g. 2080, 2081, 2082)."""

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='academic_sessions'
    )
    name = models.CharField(max_length=50, help_text='e.g. 2080, 2081-2082')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Academic Session'
        verbose_name_plural = 'Academic Sessions'
        unique_together = ['school', 'name']
        ordering = ['-name']

    def __str__(self):
        return f"{self.school.name} � {self.name}"

    def save(self, *args, **kwargs):
        # If setting this session as active, deactivate all others for this school
        if self.is_active:
            AcademicSession.objects.filter(
                school=self.school, is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class SupportTicket(models.Model):
    """A ticket raised by a school admin for super admin support."""
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='support_tickets')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.subject} - {self.school.name}"


class TicketMessage(models.Model):
    """A single reply within a support ticket thread."""
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    attachment = models.ImageField(upload_to='ticket_attachments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.sender} on {self.ticket}"


class SystemSetting(models.Model):
    """Global system settings, e.g., for super admins to upload global documents."""
    subjects_guide_pdf = models.FileField(upload_to='system_docs/', null=True, blank=True)

    # App branding — super admin can customise the name and logo shown across the app
    app_name = models.CharField(max_length=100, default='E-Natija', blank=True)
    app_logo = models.ImageField(upload_to='system_branding/', null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'
        
    @classmethod
    def get_settings(cls):
        settings, created = cls.objects.get_or_create(pk=1)
        return settings


# ---------------------------------------------------------------------------
# File cleanup signals — delete old images when replaced or record deleted
# ---------------------------------------------------------------------------
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from core.signals import delete_old_image_on_change, delete_image_on_delete

@receiver(pre_save, sender=School)
def school_logo_cleanup(sender, instance, **kwargs):
    """Delete the old school logo from storage when a new one is uploaded."""
    delete_old_image_on_change(instance, 'logo')

@receiver(post_delete, sender=School)
def school_logo_delete(sender, instance, **kwargs):
    """Delete the school logo file when the school record is deleted."""
    delete_image_on_delete(instance, 'logo')

@receiver(pre_save, sender=SystemSetting)
def system_setting_logo_cleanup(sender, instance, **kwargs):
    """Delete the old app logo from storage when a new one is uploaded."""
    delete_old_image_on_change(instance, 'app_logo')

@receiver(post_delete, sender=SystemSetting)
def system_setting_logo_delete(sender, instance, **kwargs):
    """Delete the app logo file when the system setting record is deleted."""
    delete_image_on_delete(instance, 'app_logo')
