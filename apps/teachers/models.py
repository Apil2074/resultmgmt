from django.db import models
from django.conf import settings

class Teacher(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teacher_profile'
    )
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='teachers'
    )
    sessions = models.ManyToManyField(
        'schools.AcademicSession',
        related_name='teachers',
        blank=True
    )
    sn = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=200)
    contact_number = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    photo = models.ImageField(upload_to='teacher_photos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['name']
        verbose_name = 'Teacher'
        verbose_name_plural = 'Teachers'

    def __str__(self):
        return f"{self.name} ({self.sn})" if self.sn else self.name

class TeacherSubject(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='subject_assignments')
    subject = models.ForeignKey('subjects.Subject', on_delete=models.CASCADE, related_name='assigned_teachers')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('teacher', 'subject')
        verbose_name = 'Teacher Subject Assignment'
        verbose_name_plural = 'Teacher Subject Assignments'

    def __str__(self):
        return f"{self.teacher.name} - {self.subject.name}"


# ---------------------------------------------------------------------------
# File cleanup signals — delete old images when replaced or record deleted
# ---------------------------------------------------------------------------
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from core.signals import delete_old_image_on_change, delete_image_on_delete

@receiver(pre_save, sender=Teacher)
def teacher_photo_cleanup(sender, instance, **kwargs):
    """Delete the old teacher photo from storage when a new one is uploaded."""
    delete_old_image_on_change(instance, 'photo')

@receiver(post_delete, sender=Teacher)
def teacher_photo_delete(sender, instance, **kwargs):
    """Delete the teacher photo file when the teacher record is deleted."""
    delete_image_on_delete(instance, 'photo')
