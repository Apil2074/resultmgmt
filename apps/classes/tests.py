from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.schools.models import School, AcademicSession
from apps.classes.models import Class
from apps.students.models import Student
from apps.subjects.models import Subject, StudentSubjectEnrollment

class BulkMapSubjectsTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Test School",
            address="Test Address",
            phone="1234567890",
            email="test@school.com",
            principal_name="Principal"
        )
        self.session = AcademicSession.objects.create(
            school=self.school,
            name="2083",
            is_active=True
        )
        self.user = User.objects.create_user(
            username="admin",
            password="password",
            role=User.Role.SCHOOL_ADMIN,
            school=self.school
        )
        self.class_obj = Class.objects.create(
            school=self.school,
            session=self.session,
            name="Class 9",
            section="A",
            numeric_level=9
        )
        self.student1 = Student.objects.create(
            school=self.school,
            class_obj=self.class_obj,
            name="Student One",
            roll_number="1"
        )
        self.student2 = Student.objects.create(
            school=self.school,
            class_obj=self.class_obj,
            name="Student Two",
            roll_number="2"
        )
        self.opt_sub1 = Subject.objects.create(
            school=self.school,
            class_obj=self.class_obj,
            code="OPT1",
            name="Optional Math",
            theory_credit_hour=3.0,
            subject_type=Subject.SubjectType.OPTIONAL
        )
        self.opt_sub2 = Subject.objects.create(
            school=self.school,
            class_obj=self.class_obj,
            code="OPT2",
            name="Computer Science",
            theory_credit_hour=3.0,
            subject_type=Subject.SubjectType.OPTIONAL
        )
        self.client = Client()
        self.client.login(username="admin", password="password")

    def test_bulk_map_subjects_get(self):
        url = reverse('bulk_map_subjects', kwargs={'slug': self.class_obj.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'classes/bulk_map_subjects.html')
        self.assertContains(response, "Optional Math")
        self.assertContains(response, "Computer Science")
        self.assertContains(response, "Student One")
        self.assertContains(response, "Student Two")

    def test_bulk_map_subjects_post(self):
        url = reverse('bulk_map_subjects', kwargs={'slug': self.class_obj.slug})
        post_data = {
            f'student_subjects_{self.student1.id}': [self.opt_sub1.id],
            f'student_subjects_{self.student2.id}': [self.opt_sub1.id, self.opt_sub2.id],
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302) # Redirect to class_detail
        self.assertRedirects(response, reverse('class_detail', kwargs={'slug': self.class_obj.slug}))

        # Verify mappings
        enrollments = StudentSubjectEnrollment.objects.all()
        self.assertEqual(enrollments.count(), 3)
        self.assertTrue(StudentSubjectEnrollment.objects.filter(student=self.student1, subject=self.opt_sub1).exists())
        self.assertFalse(StudentSubjectEnrollment.objects.filter(student=self.student1, subject=self.opt_sub2).exists())
        self.assertTrue(StudentSubjectEnrollment.objects.filter(student=self.student2, subject=self.opt_sub1).exists())
        self.assertTrue(StudentSubjectEnrollment.objects.filter(student=self.student2, subject=self.opt_sub2).exists())

    def test_unmap_cleanup_marks(self):
        from apps.marks.models import MarkEntry
        from apps.exams.models import Exam
        from decimal import Decimal

        # 1. Create enrollment
        enrollment = StudentSubjectEnrollment.objects.create(
            student=self.student1,
            subject=self.opt_sub1
        )
        
        # 2. Create exam
        exam = Exam.objects.create(
            school=self.school,
            session=self.session,
            name="Mid Term Exam",
            status=Exam.Status.DRAFT
        )
        
        # 3. Create marks
        mark = MarkEntry.objects.create(
            school=self.school,
            exam=exam,
            session=self.session,
            student=self.student1,
            subject=self.opt_sub1,
            theory_obtained=Decimal("85.00")
        )
        
        # Verify mark exists
        self.assertTrue(MarkEntry.objects.filter(student=self.student1, subject=self.opt_sub1).exists())
        
        # 4. Unmap student (delete enrollment)
        enrollment.delete()
        
        # Verify mark is deleted
        self.assertFalse(MarkEntry.objects.filter(student=self.student1, subject=self.opt_sub1).exists())

