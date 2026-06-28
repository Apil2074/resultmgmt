"""
Schools App — School Profile and Academic Session models
"""
from django.db import models
from django.utils import timezone


class School(models.Model):
    """Top-level tenant — all data is scoped to a school."""

    class GradingSystem(models.TextChoices):
        NEB = 'NEB', 'NEB Grading'

    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='school_logos/', null=True, blank=True)
    address = models.TextField()
    phone = models.CharField(max_length=30)
    email = models.EmailField()
    website = models.URLField(blank=True)
    establishment_year = models.PositiveIntegerField(null=True, blank=True)
    principal_name = models.CharField(max_length=150)
    exam_head_name = models.CharField(max_length=150, blank=True)
    grading_system = models.CharField(
        max_length=10,
        choices=GradingSystem.choices,
        default=GradingSystem.NEB,
    )
    is_active = models.BooleanField(default=True)
    subscription_start_date = models.DateField(null=True, blank=True)
    subscription_end_date = models.DateField(null=True, blank=True)
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
        return f"{self.school.name} — {self.name}"

    def save(self, *args, **kwargs):
        # If setting this session as active, deactivate all others for this school
        if self.is_active:
            AcademicSession.objects.filter(
                school=self.school, is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
