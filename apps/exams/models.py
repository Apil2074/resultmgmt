"""
Exams App — Exam and ExamClass models
"""
from django.db import models
from django.utils import timezone


class Exam(models.Model):
    """Exam entity (e.g. First Terminal, Annual Exam)."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='exams'
    )
    session = models.ForeignKey(
        'schools.AcademicSession', on_delete=models.CASCADE, related_name='exams'
    )
    name = models.CharField(max_length=200)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    result_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    is_locked = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='published_exams'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Exam'
        verbose_name_plural = 'Exams'
        ordering = ['-start_date', 'name']

    def __str__(self):
        return f"{self.name} — {self.session.name}"

    def publish(self, user):
        self.status = self.Status.PUBLISHED
        self.is_locked = True
        self.published_at = timezone.now()
        self.published_by = user
        self.save()

    def unlock(self):
        self.is_locked = False
        self.save()

    @property
    def is_editable(self):
        return not self.is_locked


class ExamClass(models.Model):
    """Links an exam to specific classes."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='exam_classes')
    class_obj = models.ForeignKey(
        'classes.Class', on_delete=models.CASCADE, related_name='exam_classes'
    )
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['exam', 'class_obj']
        verbose_name = 'Exam Class'

    def __str__(self):
        return f"{self.exam.name} → {self.class_obj}"
