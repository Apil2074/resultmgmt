"""
Students App — Student model
"""
from django.db import models
from django.db.models.functions import Length


class Student(models.Model):
    """Student belonging to a class within a school."""



    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='students'
    )
    class_obj = models.ForeignKey(
        'classes.Class', on_delete=models.CASCADE, related_name='students'
    )
    session = models.ForeignKey(
        'schools.AcademicSession', on_delete=models.CASCADE, null=True, blank=True, related_name='students'
    )
    roll_number = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50, blank=True, db_index=True)
    symbol_number = models.CharField(max_length=50, blank=True, db_index=True)
    gender = models.CharField(
        max_length=10,
        choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
        blank=True,
        null=True
    )
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_birth_bs = models.CharField(max_length=20, blank=True, null=True)
    parent_name = models.CharField(max_length=200, blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to='student_photos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        unique_together = ['school', 'class_obj', 'roll_number']
        ordering = ['class_obj', Length('roll_number'), 'roll_number']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'symbol_number'],
                condition=~models.Q(symbol_number=''),
                name='unique_school_symbol_number'
            ),
            models.UniqueConstraint(
                fields=['school', 'registration_number'],
                condition=~models.Q(registration_number=''),
                name='unique_school_registration_number'
            )
        ]

    def save(self, *args, **kwargs):
        if not self.session and self.class_obj:
            self.session = self.class_obj.session
            
        import datetime
        import nepali_datetime
        
        if self.date_of_birth:
            dob = self.date_of_birth
            if isinstance(dob, str):
                try:
                    parts = [int(p) for p in dob.split('-')]
                    if len(parts) == 3:
                        y, m, d = parts
                        np_date = nepali_datetime.date(y, m, d)
                        self.date_of_birth = np_date.to_datetime_date()
                        self.date_of_birth_bs = f"{y:04d}-{m:02d}-{d:02d}"
                except Exception:
                    pass
            elif isinstance(dob, (datetime.date, datetime.datetime)):
                if not self.date_of_birth_bs:
                    try:
                        np_date = nepali_datetime.date.from_datetime_date(dob)
                        self.date_of_birth_bs = np_date.strftime('%Y-%m-%d')
                    except Exception:
                        pass
        elif self.date_of_birth_bs:
            try:
                parts = [int(p) for p in self.date_of_birth_bs.split('-')]
                if len(parts) == 3:
                    y, m, d = parts
                    np_date = nepali_datetime.date(y, m, d)
                    self.date_of_birth = np_date.to_datetime_date()
            except Exception:
                pass
                
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (Roll: {self.roll_number}) — {self.class_obj}"

    @property
    def photo_url(self):
        if self.photo:
            return self.photo.url
        return '/static/images/default_student.png'

    @property
    def dob_bs(self):
        """Returns the Date of Birth in BS formatted as YYYY-MM-DD."""
        if self.date_of_birth_bs:
            return self.date_of_birth_bs
        if not self.date_of_birth:
            return ""
        import nepali_datetime
        try:
            np_date = nepali_datetime.date.from_datetime_date(self.date_of_birth)
            return np_date.strftime('%Y-%m-%d')
        except Exception:
            return self.date_of_birth.strftime('%Y-%m-%d')

    @property
    def dob_full(self):
        """Returns the Date of Birth formatted as: YYYY-MM-DD BS (YYYY-MM-DD)"""
        if not self.date_of_birth:
            return ""
        import nepali_datetime
        ad_str = self.date_of_birth.strftime('%Y-%m-%d')
        try:
            np_date = nepali_datetime.date.from_datetime_date(self.date_of_birth)
            bs_str = np_date.strftime('%Y-%m-%d')
            return f"{bs_str} BS ({ad_str} A.D)"
        except Exception:
            return f"{ad_str} A.D"


from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver

def recalculate_class_ranks(class_obj, exam):
    from apps.results.models import StudentResult
    from core.grading import calculate_ranks
    
    results = list(StudentResult.objects.filter(
        exam=exam, student__class_obj=class_obj
    ).select_related('student'))
    
    ranked = calculate_ranks(results)
    for r in ranked:
        StudentResult.objects.filter(pk=r.pk).update(class_rank=r.class_rank)

@receiver(pre_save, sender=Student)
def handle_student_class_transfer(sender, instance, **kwargs):
    """
    Clean up marks and results when a student is transferred/promoted to a different class,
    or when they are deactivated.
    """
    if not instance.pk:
        return
    try:
        old_instance = Student.objects.get(pk=instance.pk)
    except Student.DoesNotExist:
        return
        
    if old_instance.class_obj != instance.class_obj:
        from apps.marks.models import MarkEntry
        from apps.results.models import StudentResult
        from apps.exams.models import Exam
        
        # Get list of exam IDs for the student's results before deletion
        exams = list(StudentResult.objects.filter(student=instance).values_list('exam_id', flat=True))
        
        # Delete MarkEntries for subjects of the old class (cascades to SubjectResult)
        MarkEntry.objects.filter(
            student=instance,
            subject__class_obj=old_instance.class_obj
        ).delete()
        
        # Delete StudentResults to force recalculation of overall GPA and ranks
        StudentResult.objects.filter(student=instance).delete()
        
        # Recalculate ranks for remaining students in the old class
        for exam_id in exams:
            try:
                exam = Exam.objects.get(pk=exam_id)
                recalculate_class_ranks(old_instance.class_obj, exam)
            except Exam.DoesNotExist:
                continue

    if old_instance.is_active and not instance.is_active:
        from apps.results.models import StudentResult
        from apps.exams.models import Exam
        
        # Delete overall StudentResult
        exams = list(StudentResult.objects.filter(student=instance).values_list('exam_id', flat=True))
        StudentResult.objects.filter(student=instance).delete()
        
        # Recalculate ranks for each of those exams
        for exam_id in exams:
            try:
                exam = Exam.objects.get(pk=exam_id)
                recalculate_class_ranks(old_instance.class_obj, exam)
            except Exam.DoesNotExist:
                continue

@receiver(post_delete, sender=Student)
def handle_student_deletion(sender, instance, **kwargs):
    """
    Recalculate ranks for remaining students when a student is deleted.
    """
    from apps.results.models import StudentResult
    from apps.exams.models import Exam
    
    exam_ids = set(StudentResult.objects.filter(student__class_obj=instance.class_obj).values_list('exam_id', flat=True))
    for exam_id in exam_ids:
        try:
            exam = Exam.objects.get(pk=exam_id)
            recalculate_class_ranks(instance.class_obj, exam)
        except Exam.DoesNotExist:
            continue

