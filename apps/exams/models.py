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
    is_aggregate = models.BooleanField(default=False, help_text="If true, this exam's marks are aggregated from other exams.")
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


class ExamAggregationRule(models.Model):
    """Rules defining how an aggregate exam pulls marks from source exams."""
    aggregate_exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='aggregation_rules')
    source_exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='used_in_aggregations')
    weight_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight in percentage, e.g., 20.00 for 20%")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['aggregate_exam', 'source_exam']
        verbose_name = 'Exam Aggregation Rule'
        ordering = ['source_exam__start_date']

    def __str__(self):
        return f"{self.aggregate_exam.name} <- {self.weight_percentage}% of {self.source_exam.name}"


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
        ordering = ['class_obj__numeric_level', 'class_obj__name', 'class_obj__section']

    def __str__(self):
        return f"{self.exam.name} → {self.class_obj}"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.exam and self.class_obj:
            if self.exam.session_id != self.class_obj.session_id:
                raise ValidationError("Exam and Class must belong to the same Academic Session.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=ExamClass)
def cleanup_marks_and_results_on_unmap(sender, instance, **kwargs):
    """
    When a class is unmapped from an exam (ExamClass is deleted),
    clean up all MarkEntry and StudentResult records for that class and exam.
    """
    from apps.marks.models import MarkEntry
    from apps.results.models import StudentResult
    
    # Delete MarkEntries (this also cascades to SubjectResults)
    MarkEntry.objects.filter(
        exam=instance.exam,
        student__class_obj=instance.class_obj
    ).delete()
    
    # Delete StudentResults
    StudentResult.objects.filter(
        exam=instance.exam,
        student__class_obj=instance.class_obj
    ).delete()

