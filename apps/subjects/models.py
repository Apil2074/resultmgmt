"""
Subjects App — Subject, marking structure, and enrollment models
"""
from django.db import models


class Subject(models.Model):
    """Subject belonging to a class."""

    class SubjectType(models.TextChoices):
        COMPULSORY = 'COMPULSORY', 'Compulsory'
        OPTIONAL = 'OPTIONAL', 'Optional'
        NON_CREDIT = 'NON_CREDIT', 'Non-Credit'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='subjects'
    )
    class_obj = models.ForeignKey(
        'classes.Class', on_delete=models.CASCADE, related_name='subjects'
    )
    session = models.ForeignKey(
        'schools.AcademicSession', on_delete=models.CASCADE, null=True, blank=True, related_name='subjects'
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    theory_credit_hour = models.DecimalField(max_digits=4, decimal_places=2, default=3.0)
    has_practical = models.BooleanField(default=False)
    practical_credit_hour = models.DecimalField(max_digits=4, decimal_places=2, default=0.0, null=True, blank=True)
    practical_code = models.CharField(max_length=20, blank=True, default='')
    theory_full_marks = models.DecimalField(max_digits=5, decimal_places=2, default=100.0)
    theory_pass_marks = models.DecimalField(max_digits=5, decimal_places=2, default=35.0)
    practical_full_marks = models.DecimalField(max_digits=5, decimal_places=2, default=25.0, null=True, blank=True)
    practical_pass_marks = models.DecimalField(max_digits=5, decimal_places=2, default=10.0, null=True, blank=True)
    subject_type = models.CharField(
        max_length=20, choices=SubjectType.choices, default=SubjectType.COMPULSORY
    )
    order = models.PositiveIntegerField(default=0, help_text='Display order in ledger')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        unique_together = ['school', 'class_obj', 'code']
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.code}) — {self.class_obj}"

    @property
    def credit_hour(self):
        from decimal import Decimal
        th = Decimal(str(self.theory_credit_hour or '0.0'))
        pr = Decimal(str(self.practical_credit_hour or '0.0'))
        return th + pr

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.theory_credit_hour is not None and self.theory_credit_hour < 0:
            raise ValidationError("Theory credit hour cannot be negative.")
        if self.practical_credit_hour is not None and self.practical_credit_hour < 0:
            raise ValidationError("Practical credit hour cannot be negative.")
        if self.credit_hour <= 1:
            raise ValidationError("Total credit hour (Theory + Practical) must be greater than 1.")

    def save(self, *args, **kwargs):
        self.clean()
        if not self.session and self.class_obj:
            self.session = self.class_obj.session
        super().save(*args, **kwargs)

    @property
    def affects_gpa(self):
        return self.subject_type != self.SubjectType.NON_CREDIT

    @property
    def affects_pass_fail(self):
        return self.subject_type != self.SubjectType.NON_CREDIT


class StudentSubjectEnrollment(models.Model):
    """Enrollment of a student in an optional subject."""

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='subject_enrollments'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='enrolled_students'
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Student Subject Enrollment'
        unique_together = ['student', 'subject']

    def __str__(self):
        return f"{self.student.name} → {self.subject.name}"


from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=StudentSubjectEnrollment)
def delete_orphaned_mark_entries(sender, instance, **kwargs):
    """
    Delete MarkEntry records for a student when they are unmapped from an optional subject.
    """
    from apps.marks.models import MarkEntry
    MarkEntry.objects.filter(
        student=instance.student,
        subject=instance.subject
    ).delete()


@receiver(post_delete, sender=Subject)
def delete_stale_student_results_on_subject_delete(sender, instance, **kwargs):
    """
    When a Subject is deleted, delete overall StudentResult records for all students in that class
    so that overall results are forced to be recalculated and do not remain stale.
    """
    from apps.results.models import StudentResult
    StudentResult.objects.filter(student__class_obj=instance.class_obj).delete()
