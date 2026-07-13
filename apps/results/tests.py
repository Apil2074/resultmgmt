from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from apps.accounts.models import User
from apps.schools.models import School, AcademicSession
from apps.classes.models import Class
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.marks.models import MarkEntry
from apps.results.models import StudentResult
from apps.exams.models import Exam, ExamClass
from core.grading import GradingEngine, calculate_ranks


class FailureCasesMitigationTest(TestCase):
    def setUp(self):
        # Create School A
        self.school_a = School.objects.create(
            name="School A",
            address="Address A",
            phone="1234567890",
            email="school_a@test.com",
            principal_name="Principal A"
        )
        self.session_a = AcademicSession.objects.create(
            school=self.school_a,
            name="2083",
            is_active=True
        )
        
        # Create School B (for Cross-Tenant check)
        self.school_b = School.objects.create(
            name="School B",
            address="Address B",
            phone="0987654321",
            email="school_b@test.com",
            principal_name="Principal B"
        )
        self.session_b = AcademicSession.objects.create(
            school=self.school_b,
            name="2083",
            is_active=True
        )

        # Admin for School A
        self.admin = User.objects.create_user(
            username="admin_a",
            password="password",
            role=User.Role.SCHOOL_ADMIN,
            school=self.school_a
        )
        
        # Teacher for School A
        self.teacher = User.objects.create_user(
            username="teacher_a",
            password="password",
            role=User.Role.TEACHER,
            school=self.school_a
        )

        # Classes
        self.class_9a = Class.objects.create(
            school=self.school_a,
            session=self.session_a,
            name="Class 9",
            section="A",
            numeric_level=9
        )
        self.class_9b = Class.objects.create(
            school=self.school_a,
            session=self.session_a,
            name="Class 9",
            section="B",
            numeric_level=9
        )

        # Students
        self.student1 = Student.objects.create(
            school=self.school_a,
            class_obj=self.class_9a,
            name="Student One",
            roll_number="1",
            date_of_birth="2060-01-01"
        )
        self.student2 = Student.objects.create(
            school=self.school_a,
            class_obj=self.class_9a,
            name="Student Two",
            roll_number="2",
            date_of_birth="2060-01-02"
        )
        self.student3 = Student.objects.create(
            school=self.school_a,
            class_obj=self.class_9a,
            name="Student Three",
            roll_number="3",
            date_of_birth="2060-01-03"
        )

        # Subjects
        self.sub_comp = Subject.objects.create(
            school=self.school_a,
            class_obj=self.class_9a,
            code="COMP",
            name="Compulsory Subject",
            theory_credit_hour=3.0,
            subject_type=Subject.SubjectType.COMPULSORY
        )
        # Subject belonging to Class 9-B
        self.sub_mismatch = Subject.objects.create(
            school=self.school_a,
            class_obj=self.class_9b,
            code="MISMATCH",
            name="Mismatch Subject",
            theory_credit_hour=3.0,
            subject_type=Subject.SubjectType.COMPULSORY
        )

        # Exam
        self.exam = Exam.objects.create(
            school=self.school_a,
            session=self.session_a,
            name="Final Term",
            status=Exam.Status.DRAFT
        )
        ExamClass.objects.create(exam=self.exam, class_obj=self.class_9a)

        self.client = Client()

    def test_class_rank_skips_on_ties(self):
        """Failure Case 1: Tie-breaker Ranking Bug. Ranks should skip (e.g. 1, 1, 3)."""
        sr1 = StudentResult(school=self.school_a, exam=self.exam, student=self.student1, overall_gpa=Decimal("3.80"), total_marks_obtained=Decimal("450"), is_pass=True)
        sr2 = StudentResult(school=self.school_a, exam=self.exam, student=self.student2, overall_gpa=Decimal("3.80"), total_marks_obtained=Decimal("450"), is_pass=True)
        sr3 = StudentResult(school=self.school_a, exam=self.exam, student=self.student3, overall_gpa=Decimal("3.60"), total_marks_obtained=Decimal("420"), is_pass=True)

        results = [sr1, sr2, sr3]
        ranked_results = calculate_ranks(results)

        # Extract student ranks
        ranks = {r.student_id: r.class_rank for r in ranked_results}
        
        self.assertEqual(ranks[self.student1.id], 1)
        self.assertEqual(ranks[self.student2.id], 1)
        # Rank 2 is skipped, student 3 gets rank 3
        self.assertEqual(ranks[self.student3.id], 3)

    def test_subject_class_mismatch_rejected(self):
        """Failure Case 2: Subject-Class Consistency check in save_mark."""
        self.client.login(username="admin_a", password="password")
        url = reverse('save_mark')
        
        # Try to save mark for student in Class 9-A, but referencing MISMATCH subject of Class 9-B
        post_data = {
            'exam_id': self.exam.id,
            'student_id': self.student1.id,
            'subject_id': self.sub_mismatch.id,
            'theory_obtained': '75.0'
        }
        
        response = self.client.post(url, data=post_data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Subject does not belong to the student's class", response.json()['error'])

    def test_public_report_card_cross_tenant_rejected(self):
        """Failure Case 3: Public Report Card Cross-Tenant Check."""
        # Create student in School B
        student_b = Student.objects.create(
            school=self.school_b,
            class_obj=Class.objects.create(school=self.school_b, session=self.session_b, name="Class 9", section="A", numeric_level=9),
            name="Student B",
            roll_number="1",
            date_of_birth="2060-01-01"
        )
        
        # Publish the exam in School A
        self.exam.status = 'PUBLISHED'
        self.exam.save()

        # Create student results for both students so they don't redirect due to missing StudentResult
        StudentResult.objects.create(
            school=self.school_a,
            exam=self.exam,
            student=self.student1,
            overall_gpa=Decimal("3.50"),
            is_pass=True
        )
        StudentResult.objects.create(
            school=self.school_b,
            exam=self.exam, # Technically mismatch school_id, which is what we want to test
            student=student_b,
            overall_gpa=Decimal("3.50"),
            is_pass=True
        )

        # Set session auth to student_b (the attacker trying to see School A's exam)
        session = self.client.session
        session['auth_student_id'] = student_b.id
        session.save()

        url = reverse('public_report_card', kwargs={'exam_id': self.exam.id, 'student_id': student_b.id})
        response = self.client.get(url)
        # Should redirect to search with error (cross-tenant rejected)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('public_result_search'))
        
        # Now try accessing with student 1 (valid tenant)
        session['auth_student_id'] = self.student1.id
        session.save()
        
        url_valid = reverse('public_report_card', kwargs={'exam_id': self.exam.id, 'student_id': self.student1.id})
        response_valid = self.client.get(url_valid)
        self.assertEqual(response_valid.status_code, 200)

    def test_null_marks_compulsory_fails(self):
        """Failure Case 4: Subject Pass Logic on Null Marks."""
        engine = GradingEngine(system='NEB')
        ms = self.sub_comp.marking_structure
        
        # Empty mark entry with None obtained marks
        entry = MarkEntry(
            school=self.school_a,
            exam=self.exam,
            student=self.student1,
            subject=self.sub_comp,
            theory_obtained=None
        )
        
        res = engine.get_subject_result(entry, ms)
        self.assertFalse(res['is_pass'])
        self.assertEqual(res['grade'], 'NG')

    def test_teacher_unauthorized_student_class_mutations(self):
        """Failure Case 6: Teacher Privilege Escalation Checks."""
        self.client.login(username="teacher_a", password="password")
        
        # Teacher tries to add a student
        url_create_student = reverse('student_create')
        response = self.client.post(url_create_student, {
            'class_id': self.class_9a.id,
            'roll_number': '99',
            'name': 'Hacker student'
        })
        self.assertEqual(response.status_code, 302)
        # Denied and redirected to teacher dashboard by middleware
        self.assertRedirects(response, reverse('teacher_dashboard'))

        # Teacher tries to edit a student
        url_edit_student = reverse('student_edit', kwargs={'pk': self.student1.pk})
        response_edit = self.client.post(url_edit_student, {
            'name': 'Modified Student Name'
        })
        self.assertEqual(response_edit.status_code, 302)
        self.assertRedirects(response_edit, reverse('teacher_dashboard'))

        # Teacher tries to delete a student
        url_delete_student = reverse('student_delete', kwargs={'pk': self.student1.pk})
        response_delete = self.client.post(url_delete_student)
        self.assertEqual(response_delete.status_code, 302)
        self.assertRedirects(response_delete, reverse('teacher_dashboard'))

        # Teacher tries to create a class
        url_class_list = reverse('class_list')
        response_class = self.client.post(url_class_list, {
            'action': 'create',
            'name': 'Class 10',
            'section': 'A',
            'numeric_level': '10',
            'session_id': self.session_a.id
        })
        self.assertEqual(response_class.status_code, 302)
        self.assertRedirects(response_class, reverse('teacher_dashboard'))

    def test_subject_creation_non_numeric_graceful(self):
        """Failure Case 7: Non-Numeric Inputs in Subject Create/Edit."""
        self.client.login(username="admin_a", password="password")
        url_class_detail = reverse('class_detail', kwargs={'slug': self.class_9a.slug})
        
        # Try to add a subject with an invalid theory credit hour (text "invalid")
        post_data = {
            'action': 'add_subjects',
            'code': ['TEST_ERR'],
            'name': ['Test Error Subject'],
            'theory_credit_hour': ['invalid'],
            'order': ['0'],
            'subject_type': ['COMPULSORY'],
            'has_practical': ['no']
        }
        
        response = self.client.post(url_class_detail, data=post_data)
        # Should not crash with HTTP 500, but redirect back with error message
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, url_class_detail)

    def test_pass_fail_report_filters(self):
        """Verify that pass_fail_report view filters and computes analytics correctly."""
        self.client.login(username="admin_a", password="password")
        
        # Create a StudentResult for student1 (Class 9-A, Male)
        StudentResult.objects.create(
            school=self.school_a,
            exam=self.exam,
            student=self.student1,
            overall_gpa=Decimal("3.80"),
            final_grade="A",
            is_pass=True
        )

        url = reverse('pass_fail_report', kwargs={'exam_id': self.exam.id})
        
        # Test without filters
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('grade_dist_json', response.context)
        self.assertIn('gpa_dist_json', response.context)

        # Test filtering by class
        response_filtered = self.client.get(url + f"?class_id={self.class_9a.id}")
        self.assertEqual(response_filtered.status_code, 200)
        
        # Test filtering by gender
        response_gender = self.client.get(url + "?gender=M")
        self.assertEqual(response_gender.status_code, 200)

    def test_merit_list_filters(self):
        """Verify that merit_list view filters correctly."""
        self.client.login(username="admin_a", password="password")
        
        # Create results
        StudentResult.objects.create(
            school=self.school_a,
            exam=self.exam,
            student=self.student1,
            overall_gpa=Decimal("3.80"),
            is_pass=True
        )
        
        url = reverse('merit_list', kwargs={'exam_id': self.exam.id})
        
        # Filter by Class 9-A
        response = self.client.get(url + f"?class_id={self.class_9a.id}")
        self.assertEqual(response.status_code, 200)

    def test_single_page_pdf_generation(self):
        """Verify that generated marksheet PDFs for both templates have exactly 1 page."""
        self.client.login(username="admin_a", password="password")
        
        from apps.reports.pdf_generators import MarksheetPDFGenerator, NEB11MarksheetPDFGenerator
        from apps.marks.models import MarkEntry
        
        # Get entries
        entries = MarkEntry.objects.filter(student=self.student1, exam=self.exam)
        
        # Create standard PDF
        gen = MarksheetPDFGenerator(self.school_a, self.exam, self.student1, None, entries)
        pdf_data = gen.generate()
        
        # Create NEB PDF
        gen_neb = NEB11MarksheetPDFGenerator(self.school_a, self.exam, self.student1, None, entries)
        pdf_data_neb = gen_neb.generate()
        
        # Count pages
        try:
            import io
            from pypdf import PdfReader
            
            reader = PdfReader(io.BytesIO(pdf_data))
            self.assertEqual(len(reader.pages), 1, f"Standard marksheet PDF has {len(reader.pages)} pages instead of 1")
            
            reader_neb = PdfReader(io.BytesIO(pdf_data_neb))
            self.assertEqual(len(reader_neb.pages), 1, f"NEB marksheet PDF has {len(reader_neb.pages)} pages instead of 1")
            
        except ImportError:
            # Fallback if pypdf is not installed
            page_count_std = pdf_data.count(b"/Type /Page") - pdf_data.count(b"/Type /Pages")
            self.assertEqual(page_count_std, 1, f"Standard marksheet PDF has {page_count_std} pages instead of 1")
            
            page_count_neb = pdf_data_neb.count(b"/Type /Page") - pdf_data_neb.count(b"/Type /Pages")
            self.assertEqual(page_count_neb, 1, f"NEB marksheet PDF has {page_count_neb} pages instead of 1")

    def test_large_number_of_subjects_single_page_pdf_generation(self):
        """Verify that marksheets with 10 subjects (producing dense tables) still generate exactly 1 page."""
        self.client.login(username="admin_a", password="password")
        
        from apps.subjects.models import Subject
        from apps.marks.models import MarkEntry
        from apps.reports.pdf_generators import MarksheetPDFGenerator, NEB11MarksheetPDFGenerator
        
        # Create additional subjects to reach 10 subjects
        for i in range(1, 11):
            sub = Subject.objects.create(
                school=self.school_a,
                class_obj=self.class_9a,
                name=f"Dense Subject {i}",
                code=f"DS{i:02d}",
                theory_credit_hour=3.0,
                has_practical=(i % 2 == 0), # alternate practicals to make table larger
                practical_credit_hour=1.0 if (i % 2 == 0) else 0.0,
                subject_type='COMPULSORY',
                order=10 + i
            )
            MarkEntry.objects.create(
                school=self.school_a,
                student=self.student1,
                exam=self.exam,
                subject=sub,
                theory_obtained=45.0,
                internal_obtained=18.0 if sub.has_practical else None
            )
            
        # Verify total subjects is now 10
        entries = MarkEntry.objects.filter(student=self.student1, exam=self.exam)
        self.assertEqual(entries.count(), 10)
        
        # Process marksheet generators
        gen = MarksheetPDFGenerator(self.school_a, self.exam, self.student1, None, entries)
        pdf_data = gen.generate()
        
        gen_neb = NEB11MarksheetPDFGenerator(self.school_a, self.exam, self.student1, None, entries)
        pdf_data_neb = gen_neb.generate()
        
        # Verify page count is exactly 1 page
        try:
            import io
            from pypdf import PdfReader
            
            reader = PdfReader(io.BytesIO(pdf_data))
            self.assertEqual(len(reader.pages), 1, f"Dense standard marksheet has {len(reader.pages)} pages instead of 1")
            
            reader_neb = PdfReader(io.BytesIO(pdf_data_neb))
            self.assertEqual(len(reader_neb.pages), 1, f"Dense NEB marksheet has {len(reader_neb.pages)} pages instead of 1")
        except ImportError:
            page_count_std = pdf_data.count(b"/Type /Page") - pdf_data.count(b"/Type /Pages")
            self.assertEqual(page_count_std, 1, f"Dense standard marksheet has {page_count_std} pages instead of 1")
            
            page_count_neb = pdf_data_neb.count(b"/Type /Page") - pdf_data_neb.count(b"/Type /Pages")
            self.assertEqual(page_count_neb, 1, f"Dense NEB marksheet has {page_count_neb} pages instead of 1")
