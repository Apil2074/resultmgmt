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
        return self.theory_credit_hour + (self.practical_credit_hour or Decimal('0.0'))

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.theory_credit_hour is not None and self.theory_credit_hour < 0:
            raise ValidationError("Theory credit hour cannot be negative.")
        if self.practical_credit_hour is not None and self.practical_credit_hour < 0:
            raise ValidationError("Practical credit hour cannot be negative.")

    def save(self, *args, **kwargs):
        self.clean()
        if not self.session and self.class_obj:
            self.session = self.class_obj.session
        super().save(*args, **kwargs)
        
        # Auto-create or update SubjectMarkingStructure
        from apps.subjects.models import SubjectMarkingStructure
        pass_marks = 35
        
        sms, created = SubjectMarkingStructure.objects.get_or_create(
            subject=self,
            defaults={
                'has_theory': True,
                'theory_full_marks': 100,
                'theory_pass_marks': pass_marks,
                'has_internal': self.has_practical,
                'internal_full_marks': 100 if self.has_practical else 0,
                'internal_pass_marks': pass_marks if self.has_practical else 0,
            }
        )
        if not created:
            sms.has_internal = self.has_practical
            if not self.has_practical:
                sms.internal_full_marks = 0
                sms.internal_pass_marks = 0
            else:
                # Only set defaults if it was previously 0 or None
                if not sms.internal_full_marks:
                    sms.internal_full_marks = 25  # A more reasonable default for practicals
                if not sms.internal_pass_marks:
                    sms.internal_pass_marks = 10
            sms.save()

    @property
    def affects_gpa(self):
        return self.subject_type != self.SubjectType.NON_CREDIT

    @property
    def affects_pass_fail(self):
        return self.subject_type != self.SubjectType.NON_CREDIT


class SubjectMarkingStructure(models.Model):
    """Defines the marking structure for a subject (theory + internal components)."""

    subject = models.OneToOneField(
        Subject, on_delete=models.CASCADE, related_name='marking_structure'
    )
    # Theory component
    has_theory = models.BooleanField(default=True)
    theory_full_marks = models.PositiveIntegerField(default=100)
    theory_pass_marks = models.PositiveIntegerField(default=40)

    # Internal / Practical component
    has_internal = models.BooleanField(default=False)
    internal_full_marks = models.PositiveIntegerField(default=25, null=True, blank=True)
    internal_pass_marks = models.PositiveIntegerField(default=10, null=True, blank=True)

    class Meta:
        verbose_name = 'Subject Marking Structure'

    def __str__(self):
        return f"Marking — {self.subject.name}"

    @property
    def total_full_marks(self):
        total = 0
        if self.has_theory:
            total += self.theory_full_marks
        if self.has_internal:
            total += (self.internal_full_marks or 0)
        return total

    @property
    def total_pass_marks(self):
        total = 0
        if self.has_theory:
            total += self.theory_pass_marks
        if self.has_internal:
            total += (self.internal_pass_marks or 0)
        return total

    def clean(self):
        super().clean()
        if self.pk:
            from django.core.exceptions import ValidationError
            from apps.marks.models import MarkEntry
            exceeding_theory = MarkEntry.objects.filter(
                subject=self.subject,
                theory_obtained__gt=self.theory_full_marks
            ).exists()
            if exceeding_theory:
                raise ValidationError("Cannot reduce theory full marks because some students already have marks exceeding the new limit.")
            
            if self.has_internal and self.internal_full_marks is not None:
                exceeding_internal = MarkEntry.objects.filter(
                    subject=self.subject,
                    internal_obtained__gt=self.internal_full_marks
                ).exists()
                if exceeding_internal:
                    raise ValidationError("Cannot reduce internal full marks because some students already have marks exceeding the new limit.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


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
