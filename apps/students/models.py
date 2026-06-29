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
