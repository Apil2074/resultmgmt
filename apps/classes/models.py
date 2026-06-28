"""
Classes App — Class and ClassTeacher models
"""
from django.db import models


class Class(models.Model):
    """Represents a class (e.g. Class 10, Section A)."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='classes'
    )
    session = models.ForeignKey(
        'schools.AcademicSession', on_delete=models.CASCADE, related_name='classes'
    )
    name = models.CharField(max_length=100, help_text='e.g. Class 10, Grade 9')
    section = models.CharField(max_length=10, blank=True, help_text='e.g. A, B, C')
    numeric_level = models.PositiveIntegerField(default=0, help_text='Sort order (e.g., 1 for Nursery, 10 for Class 10)')
    slug = models.SlugField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Class'
        verbose_name_plural = 'Classes'
        unique_together = ['school', 'session', 'name', 'section']
        ordering = ['numeric_level', 'name', 'section']

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        import re
        if not self.numeric_level or self.numeric_level == 0:
            match = re.search(r'\d+', self.name)
            if match:
                self.numeric_level = int(match.group())
        if not self.slug:
            self.slug = slugify(f"{self.full_name}-{self.session.name}")
        super().save(*args, **kwargs)

    def __str__(self):
        section = f' ({self.section})' if self.section else ''
        return f"{self.prefixed_name}{section} — {self.session.name}"

    @property
    def prefixed_name(self):
        name = self.name.strip()
        name_lower = name.lower()
        if name_lower.startswith('class') or name_lower.startswith('grade'):
            return name
        return f"Class {name}"

    @property
    def full_name(self):
        section = f' {self.section}' if self.section else ''
        return f"{self.prefixed_name}{section}"

    def student_count(self):
        return self.students.count()


class ClassTeacher(models.Model):
    """Class teacher assignment."""

    class_obj = models.OneToOneField(
        Class, on_delete=models.CASCADE, related_name='class_teacher'
    )
    teacher = models.ForeignKey(
        'teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='class_teacher_roles'
    )
    name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Class Teacher'
        verbose_name_plural = 'Class Teachers'

    def __str__(self):
        return f"{self.name} — {self.class_obj}"
