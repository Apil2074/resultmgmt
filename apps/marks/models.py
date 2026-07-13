"""
Marks App — MarkEntry model
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


class MarkEntry(models.Model):
    """Mark entry for a student in a subject for an exam."""

    class SpecialValue(models.TextChoices):
        ABSENT = 'AB', 'Absent'
        WITHHELD = 'WH', 'Withheld'
        EXEMPTED = 'EX', 'Exempted'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='mark_entries'
    )
    exam = models.ForeignKey(
        'exams.Exam', on_delete=models.CASCADE, related_name='mark_entries'
    )
    session = models.ForeignKey(
        'schools.AcademicSession', on_delete=models.CASCADE, null=True, blank=True, related_name='mark_entries'
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='mark_entries'
    )
    subject = models.ForeignKey(
        'subjects.Subject', on_delete=models.CASCADE, related_name='mark_entries'
    )

    # Special value override
    special_value = models.CharField(
        max_length=2, choices=SpecialValue.choices, null=True, blank=True
    )

    # Theory marks
    theory_obtained = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)]
    )

    # Internal / Practical marks
    internal_obtained = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)]
    )

    # Attendance
    present_days = models.PositiveIntegerField(null=True, blank=True)
    total_days = models.PositiveIntegerField(null=True, blank=True)

    entered_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='entered_marks'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mark Entry'
        verbose_name_plural = 'Mark Entries'
        unique_together = ['exam', 'student', 'subject']
        ordering = ['student__roll_number', 'subject__order']

    def __str__(self):
        return f"{self.student.name} — {self.subject.name} — {self.exam.name}"

    @property
    def attendance_percentage(self):
        if self.present_days is not None and self.total_days:
            return round((self.present_days / self.total_days) * 100, 2)
        return None

    @property
    def is_special(self):
        return self.special_value is not None

    @property
    def total_obtained(self):
        if self.is_special:
            return None
        theory = self.theory_obtained or 0
        internal = self.internal_obtained or 0
        return theory + internal

    def clean(self):
        if self.student and not self.student.is_active:
            raise ValidationError("Cannot enter marks for an inactive student.")

        if self.present_days is not None:
            if self.present_days < 0:
                raise ValidationError("Present days cannot be negative.")
        if self.total_days is not None:
            if self.total_days < 0:
                raise ValidationError("Total days cannot be negative.")
        if self.present_days is not None and self.total_days is not None:
            if self.present_days > self.total_days:
                raise ValidationError("Present days cannot exceed total days.")

        if not self.is_special:
            try:
                struct = self.subject.marking_structure
            except Exception:
                return
            
            from decimal import Decimal

            theory_obtained = self.theory_obtained
            if theory_obtained is not None:
                try:
                    theory_obtained = Decimal(str(theory_obtained))
                except Exception:
                    raise ValidationError("Invalid theory marks format.")
                if theory_obtained < 0:
                    raise ValidationError("Theory marks cannot be negative.")
                if theory_obtained > Decimal(struct.theory_full_marks):
                    raise ValidationError(
                        f"Theory marks ({theory_obtained}) cannot exceed "
                        f"full marks ({struct.theory_full_marks})"
                    )

            internal_obtained = self.internal_obtained
            if internal_obtained is not None:
                if not struct.has_internal:
                    raise ValidationError("Cannot enter internal/practical marks for a subject without a practical component.")
                try:
                    internal_obtained = Decimal(str(internal_obtained))
                except Exception:
                    raise ValidationError("Invalid internal marks format.")
                if internal_obtained < 0:
                    raise ValidationError("Internal marks cannot be negative.")
                if internal_obtained > Decimal(struct.internal_full_marks):
                    raise ValidationError(
                        f"Internal marks ({internal_obtained}) cannot exceed "
                        f"full marks ({struct.internal_full_marks})"
                    )

    def save(self, *args, **kwargs):
        if not self.session and self.exam:
            self.session = self.exam.session
        self.clean()
        super().save(*args, **kwargs)
