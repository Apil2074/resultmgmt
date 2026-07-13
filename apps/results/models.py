"""
Results App — SubjectResult and StudentResult models
"""
from django.db import models


class SubjectResult(models.Model):
    """Calculated result for a student in one subject of an exam."""

    mark_entry = models.OneToOneField(
        'marks.MarkEntry', on_delete=models.CASCADE, related_name='subject_result'
    )
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='subject_results'
    )
    session = models.ForeignKey(
        'schools.AcademicSession', on_delete=models.CASCADE, null=True, blank=True, related_name='subject_results'
    )

    # Grade computation
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=5, blank=True)
    gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    # Theory sub-result
    theory_grade_point = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    theory_grade = models.CharField(max_length=5, blank=True)

    # Internal sub-result
    internal_grade_point = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    internal_grade = models.CharField(max_length=5, blank=True)

    is_pass = models.BooleanField(default=False)
    remarks = models.CharField(max_length=100, blank=True)

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Subject Result'

    def save(self, *args, **kwargs):
        if not self.session and self.mark_entry and self.mark_entry.exam:
            self.session = self.mark_entry.exam.session
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.mark_entry.student.name} — "
            f"{self.mark_entry.subject.name} — "
            f"GP: {self.grade_point} Grade: {self.grade}"
        )


class StudentResult(models.Model):
    """Aggregated result for a student in an exam."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='student_results'
    )
    exam = models.ForeignKey(
        'exams.Exam', on_delete=models.CASCADE, related_name='student_results'
    )
    session = models.ForeignKey(
        'schools.AcademicSession', on_delete=models.CASCADE, null=True, blank=True, related_name='student_results'
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='student_results'
    )

    # Aggregated data
    total_credit_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    total_marks_obtained = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_full_marks = models.PositiveIntegerField(default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # GPA & Grading
    overall_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    final_grade = models.CharField(max_length=5, blank=True)

    # Rank
    class_rank = models.PositiveIntegerField(null=True, blank=True)
    section_rank = models.PositiveIntegerField(null=True, blank=True)

    # Status
    is_pass = models.BooleanField(default=False)
    failed_subjects = models.JSONField(default=list, blank=True)


    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Student Result'
        unique_together = ['exam', 'student']
        ordering = ['class_rank', 'student__roll_number']

    def save(self, *args, **kwargs):
        if not self.session and self.exam:
            self.session = self.exam.session
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.name} — {self.exam.name} — GPA: {self.overall_gpa}"


class GradeScale(models.Model):
    """Custom grading scale for a school."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='grade_scales'
    )
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Grade Scale'
        unique_together = ['school']

    def __str__(self):
        return f"{self.name}"


class GradeScaleEntry(models.Model):
    """One row in a grading scale table."""

    scale = models.ForeignKey(GradeScale, on_delete=models.CASCADE, related_name='entries')
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=5)
    grade_point = models.DecimalField(max_digits=4, decimal_places=2)
    description = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-min_percentage']

    def __str__(self):
        return f"{self.grade} ({self.min_percentage}% – {self.max_percentage}%)"
