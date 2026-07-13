"""
test_20_cases.py — Comprehensive 20 Real-World Failure Case Tests
=================================================================

Covers:
  1.  Login with disabled account
  2.  Login with expired school subscription
  3.  Subscription boundary (expires today vs tomorrow)
  4.  Student save with invalid Nepali date
  5.  ExamClass cross-session mismatch prevented by clean()
  6.  MarkEntry save blocked for inactive student
  7.  MarkEntry theory marks exceed full marks
  8.  MarkEntry internal marks for subject without practical
  9.  MarkEntry attendance: present_days > total_days
 10.  SubjectMarkingStructure: cannot reduce full marks below existing entry
 11.  Duplicate roll number in same class blocked
 12.  Teacher-school cross-school subject assignment blocked
 13.  AcademicSession: setting one active deactivates others
 14.  Subject deletion cascades to StudentResult cleanup
 15.  Student class transfer clears old marks and results
 16.  GradingEngine: all-special-value entries yield no grade
 17.  GradingEngine: zero credit-hour subjects excluded from GPA
 18.  ResultProcessingService: missing mark entries auto-created as AB
 19.  calculate_ranks: failed students get no rank; ties share rank
 20.  save_mark AJAX: locked exam returns 403; unlocking allows save
"""

import os
import sys
import django
from decimal import Decimal
from datetime import date, timedelta

# ── Bootstrap ────────────────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
django.setup()

# ── Django imports ────────────────────────────────────────────────────────────
from django.test import TestCase, Client, RequestFactory
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.schools.models import School, AcademicSession
from apps.classes.models import Class
from apps.subjects.models import Subject, SubjectMarkingStructure, StudentSubjectEnrollment
from apps.students.models import Student
from apps.teachers.models import Teacher, TeacherSubject
from apps.exams.models import Exam, ExamClass
from apps.marks.models import MarkEntry
from apps.results.models import SubjectResult, StudentResult
from apps.results.services import ResultProcessingService
from core.grading import GradingEngine, calculate_ranks

User = get_user_model()

# ── Helper factory ────────────────────────────────────────────────────────────

def make_school(name='Test School', sub_start=None, sub_end=None):
    return School.objects.create(
        name=name,
        address='Kathmandu',
        phone='9800000000',
        email=f'{name.lower().replace(" ", "")}@test.com',
        principal_name='Test Principal',
        grading_system='NEB',
        subscription_start_date=sub_start,
        subscription_end_date=sub_end,
    )


def make_session(school, name='2081', active=True):
    session = AcademicSession.objects.create(
        school=school, name=name,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        is_active=active,
    )
    return session


def make_class(school, session, name='Class 11', section='A'):
    return Class.objects.create(
        school=school, session=session, name=name, section=section
    )


def make_subject(school, class_obj, code='ENG', name='English',
                 has_practical=False, subject_type='COMPULSORY'):
    return Subject.objects.create(
        school=school, class_obj=class_obj, code=code, name=name,
        has_practical=has_practical, subject_type=subject_type,
        theory_credit_hour=Decimal('4.0'),
        practical_credit_hour=Decimal('2.0') if has_practical else Decimal('0.0'),
    )


def make_student(school, class_obj, roll='1', name='Test Student'):
    return Student.objects.create(
        school=school, class_obj=class_obj, roll_number=roll, name=name
    )


def make_exam(school, session, name='Terminal 1'):
    return Exam.objects.create(
        school=school, session=session, name=name,
        status=Exam.Status.DRAFT
    )


def make_user(school, username, role=User.Role.SCHOOL_ADMIN, active=True):
    u = User.objects.create_user(
        username=username, password='Pass@1234', school=school,
        role=role, is_active=active
    )
    return u


# ══════════════════════════════════════════════════════════════════════════════
# CASE 1: Login with a disabled (is_active=False) user account
# ══════════════════════════════════════════════════════════════════════════════
class Case01_DisabledAccountLogin(TestCase):
    """
    FAIL SCENARIO: A user whose `is_active=False` tries to log in.
    Expected: Login is rejected with 'Your account is disabled.' message.
    """

    def setUp(self):
        self.school = make_school('School01')
        self.user = make_user(self.school, 'disabled_user', active=False)
        self.client = Client()

    def test_disabled_user_cannot_login(self):
        response = self.client.post('/accounts/login/', {
            'username': 'disabled_user',
            'password': 'Pass@1234',
        })
        self.assertEqual(response.status_code, 200)  # stays on login page
        messages_list = list(response.context['messages'])
        self.assertTrue(
            any('disabled' in str(m).lower() for m in messages_list),
            f"Expected 'disabled' message. Got: {[str(m) for m in messages_list]}"
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def tearDown(self):
        self.user.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 2: Login with expired school subscription
# ══════════════════════════════════════════════════════════════════════════════
class Case02_ExpiredSubscriptionLogin(TestCase):
    """
    FAIL SCENARIO: A school's subscription has expired yesterday.
    Expected: Login blocked with subscription-expired message.
    """

    def setUp(self):
        yesterday = date.today() - timedelta(days=1)
        self.school = make_school('School02',
                                  sub_start=date(2024, 1, 1),
                                  sub_end=yesterday)
        self.user = make_user(self.school, 'school_admin2')
        self.client = Client()

    def test_expired_subscription_blocks_login(self):
        response = self.client.post('/accounts/login/', {
            'username': 'school_admin2',
            'password': 'Pass@1234',
        })
        self.assertEqual(response.status_code, 200)
        messages_list = list(response.context['messages'])
        self.assertTrue(
            any('subscription' in str(m).lower() for m in messages_list),
            f"Expected 'subscription' message. Got: {[str(m) for m in messages_list]}"
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def tearDown(self):
        self.user.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 3: Subscription boundary — expires today (active) vs yesterday (expired)
# ══════════════════════════════════════════════════════════════════════════════
class Case03_SubscriptionBoundary(TestCase):
    """
    FAIL SCENARIO: Ambiguous boundary — subscription end_date == today.
    has_active_subscription() should return False (expired) per model logic.
    """

    def test_expires_today_is_not_active(self):
        school = make_school('School03a',
                             sub_start=date(2024, 1, 1),
                             sub_end=date.today())
        # today < today is False → subscription is expired
        self.assertFalse(school.has_active_subscription(),
                         "Subscription expiring today should NOT be active (end < now fails)")
        school.delete()

    def test_expires_tomorrow_is_active(self):
        school = make_school('School03b',
                             sub_start=date(2024, 1, 1),
                             sub_end=date.today() + timedelta(days=1))
        self.assertTrue(school.has_active_subscription())
        school.delete()

    def test_no_dates_is_active(self):
        """Schools with no subscription dates set should be treated as active."""
        school = make_school('School03c')
        self.assertTrue(school.has_active_subscription())
        school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 4: Student model — nepali_datetime conversion error is silently ignored
# ══════════════════════════════════════════════════════════════════════════════
class Case04_StudentInvalidNepaliDate(TestCase):
    """
    FAIL SCENARIO: date_of_birth is set to a BS date string (like '2081-01-01')
    but the student save() tries to parse it as a Gregorian date first.
    The exception is caught silently, leaving date_of_birth_bs blank.
    """

    def setUp(self):
        self.school = make_school('School04')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)

    def test_student_saves_with_valid_gregorian_dob(self):
        student = Student.objects.create(
            school=self.school, class_obj=self.cls,
            roll_number='1', name='Priya Sharma',
            date_of_birth=date(2006, 4, 14)  # AD date — valid
        )
        student.refresh_from_db()
        # date_of_birth should remain as-is
        self.assertEqual(student.date_of_birth, date(2006, 4, 14))
        # date_of_birth_bs should be auto-populated
        self.assertIsNotNone(student.date_of_birth_bs,
                             "date_of_birth_bs should be set from AD date via nepali_datetime")
        student.delete()

    def test_student_saves_with_malformed_date(self):
        """
        Malformed date_of_birth_bs should not crash the save() — exception is swallowed.
        This tests that silent failure is happening (it is, per the model code).
        """
        student = Student(
            school=self.school, class_obj=self.cls,
            roll_number='2', name='Ram Bahadur',
        )
        student.date_of_birth = None
        student.date_of_birth_bs = 'INVALID-DATE'
        # Should not raise — exception is caught silently in save()
        student.save()
        student.refresh_from_db()
        # date_of_birth remains None because parsing failed silently
        self.assertIsNone(student.date_of_birth)
        student.delete()

    def tearDown(self):
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 5: ExamClass clean() blocks cross-session assignment
# ══════════════════════════════════════════════════════════════════════════════
class Case05_ExamClassCrossSession(TestCase):
    """
    FAIL SCENARIO: An ExamClass links an Exam from Session A to a Class from Session B.
    Expected: ValidationError raised by ExamClass.clean().
    """

    def setUp(self):
        self.school = make_school('School05')
        self.session_a = make_session(self.school, name='2081A', active=True)
        self.session_b = make_session(self.school, name='2081B', active=False)
        self.cls_a = make_class(self.school, self.session_a, name='Class 11', section='A')
        self.cls_b = make_class(self.school, self.session_b, name='Class 11', section='B')
        self.exam = make_exam(self.school, self.session_a)

    def test_cross_session_examclass_raises(self):
        ec = ExamClass(exam=self.exam, class_obj=self.cls_b)
        with self.assertRaises(ValidationError) as ctx:
            ec.clean()
        self.assertIn('same Academic Session', str(ctx.exception))

    def test_same_session_examclass_passes(self):
        ec = ExamClass.objects.create(exam=self.exam, class_obj=self.cls_a)
        self.assertIsNotNone(ec.pk)
        ec.delete()

    def tearDown(self):
        self.exam.delete()
        self.cls_a.delete()
        self.cls_b.delete()
        self.session_a.delete()
        self.session_b.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 6: MarkEntry blocked for inactive student
# ══════════════════════════════════════════════════════════════════════════════
class Case06_MarkEntryInactiveStudent(TestCase):
    """
    FAIL SCENARIO: Teacher tries to enter marks for a deactivated student.
    Expected: ValidationError from MarkEntry.clean() — 'inactive student'.
    """

    def setUp(self):
        self.school = make_school('School06')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.subject = make_subject(self.school, self.cls)
        self.exam = make_exam(self.school, self.session)
        ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls, roll='1')
        # Deactivate student
        self.student.is_active = False
        self.student.save()

    def test_mark_entry_blocked_for_inactive_student(self):
        me = MarkEntry(
            exam=self.exam, school=self.school, student=self.student,
            subject=self.subject, theory_obtained=Decimal('60')
        )
        with self.assertRaises(ValidationError) as ctx:
            me.clean()
        self.assertIn('inactive', str(ctx.exception).lower())

    def tearDown(self):
        self.exam.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 7: MarkEntry theory marks exceed subject full marks
# ══════════════════════════════════════════════════════════════════════════════
class Case07_MarkEntryExceedsFullMarks(TestCase):
    """
    FAIL SCENARIO: Theory marks entered as 110 when full marks = 100.
    Expected: ValidationError — 'cannot exceed full marks'.
    """

    def setUp(self):
        self.school = make_school('School07')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.subject = make_subject(self.school, self.cls, code='MAT', name='Math')
        self.exam = make_exam(self.school, self.session)
        ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls)
        # Ensure full marks = 100
        ms = self.subject.marking_structure
        ms.theory_full_marks = 100
        ms.save()

    def test_marks_exceeding_full_marks_raises(self):
        me = MarkEntry(
            exam=self.exam, school=self.school, student=self.student,
            subject=self.subject, theory_obtained=Decimal('110')
        )
        with self.assertRaises(ValidationError) as ctx:
            me.clean()
        self.assertIn('exceed', str(ctx.exception).lower())

    def test_marks_at_full_marks_passes(self):
        me = MarkEntry(
            exam=self.exam, school=self.school, student=self.student,
            subject=self.subject, theory_obtained=Decimal('100')
        )
        # Should not raise
        me.clean()

    def tearDown(self):
        self.exam.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 8: MarkEntry internal marks for subject without practical component
# ══════════════════════════════════════════════════════════════════════════════
class Case08_InternalMarksNoPractical(TestCase):
    """
    FAIL SCENARIO: Internal marks entered for a pure-theory subject.
    Expected: ValidationError — 'without a practical component'.
    """

    def setUp(self):
        self.school = make_school('School08')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        # has_practical=False (pure theory subject)
        self.subject = make_subject(self.school, self.cls, code='ACC', name='Accounts',
                                    has_practical=False)
        self.exam = make_exam(self.school, self.session)
        ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls)

    def test_internal_marks_on_theory_subject_raises(self):
        me = MarkEntry(
            exam=self.exam, school=self.school, student=self.student,
            subject=self.subject,
            theory_obtained=Decimal('50'),
            internal_obtained=Decimal('20'),  # invalid!
        )
        with self.assertRaises(ValidationError) as ctx:
            me.clean()
        self.assertIn('practical', str(ctx.exception).lower())

    def tearDown(self):
        self.exam.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 9: MarkEntry attendance: present_days > total_days
# ══════════════════════════════════════════════════════════════════════════════
class Case09_AttendanceExceedsTotalDays(TestCase):
    """
    FAIL SCENARIO: present_days (200) > total_days (150).
    Expected: ValidationError — 'cannot exceed total days'.
    """

    def setUp(self):
        self.school = make_school('School09')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.subject = make_subject(self.school, self.cls, code='PHY', name='Physics')
        self.exam = make_exam(self.school, self.session)
        ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls)

    def test_present_exceeds_total_raises(self):
        me = MarkEntry(
            exam=self.exam, school=self.school, student=self.student,
            subject=self.subject, present_days=200, total_days=150
        )
        with self.assertRaises(ValidationError) as ctx:
            me.clean()
        self.assertIn('exceed', str(ctx.exception).lower())

    def test_negative_present_days_raises(self):
        me = MarkEntry(
            exam=self.exam, school=self.school, student=self.student,
            subject=self.subject, present_days=-1, total_days=150
        )
        with self.assertRaises(ValidationError) as ctx:
            me.clean()
        self.assertIn('negative', str(ctx.exception).lower())

    def tearDown(self):
        self.exam.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 10: SubjectMarkingStructure: reducing full marks below existing entries
# ══════════════════════════════════════════════════════════════════════════════
class Case10_ReduceFullMarksBelowExistingEntry(TestCase):
    """
    FAIL SCENARIO: A student has theory_obtained=90, but admin tries to set
    theory_full_marks=80.  SubjectMarkingStructure.clean() should block this.
    """

    def setUp(self):
        self.school = make_school('School10')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.subject = make_subject(self.school, self.cls, code='CHE', name='Chemistry')
        self.exam = make_exam(self.school, self.session)
        ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls)
        # Save a mark entry with 90/100
        self.me = MarkEntry.objects.create(
            exam=self.exam, school=self.school,
            student=self.student, subject=self.subject,
            theory_obtained=Decimal('90')
        )

    def test_reducing_full_marks_below_existing_entry_raises(self):
        ms = self.subject.marking_structure
        ms.theory_full_marks = 80  # 90 > 80 — existing entry would exceed new limit
        with self.assertRaises(ValidationError) as ctx:
            ms.clean()
        self.assertIn('reduce', str(ctx.exception).lower())

    def test_keeping_full_marks_same_passes(self):
        ms = self.subject.marking_structure
        ms.theory_full_marks = 100  # same value — OK
        ms.clean()  # Should not raise

    def tearDown(self):
        self.me.delete()
        self.exam.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 11: Duplicate roll number blocked by unique_together constraint
# ══════════════════════════════════════════════════════════════════════════════
class Case11_DuplicateRollNumber(TestCase):
    """
    FAIL SCENARIO: Two students in the same class get roll number '5'.
    Expected: IntegrityError / database error on second create.
    """

    def setUp(self):
        self.school = make_school('School11')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.s1 = make_student(self.school, self.cls, roll='5', name='Student A')

    def test_duplicate_roll_number_raises(self):
        from django.db import IntegrityError
        with self.assertRaises((IntegrityError, ValidationError)):
            Student.objects.create(
                school=self.school, class_obj=self.cls,
                roll_number='5', name='Student B'
            )

    def tearDown(self):
        self.s1.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 12: Teacher cross-school subject assignment blocked
# ══════════════════════════════════════════════════════════════════════════════
class Case12_CrossSchoolTeacherAssignment(TestCase):
    """
    FAIL SCENARIO: Teacher from School A assigned to a Subject from School B.
    Expected: ValidationError from TeacherSubject.clean().
    """

    def setUp(self):
        self.school_a = make_school('School12A')
        self.school_b = make_school('School12B')
        self.session_a = make_session(self.school_a, name='2081')
        self.session_b = make_session(self.school_b, name='2081')
        self.cls_b = make_class(self.school_b, self.session_b)
        self.subject_b = make_subject(self.school_b, self.cls_b, code='ENG', name='English')
        self.teacher_a = Teacher.objects.create(
            school=self.school_a, name='Mr. Sharma'
        )

    def test_cross_school_assignment_raises(self):
        ts = TeacherSubject(teacher=self.teacher_a, subject=self.subject_b)
        with self.assertRaises(ValidationError) as ctx:
            ts.clean()
        self.assertIn('same school', str(ctx.exception).lower())

    def tearDown(self):
        self.teacher_a.delete()
        self.cls_b.delete()
        self.session_a.delete()
        self.session_b.delete()
        self.school_a.delete()
        self.school_b.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 13: AcademicSession — setting one active deactivates all others
# ══════════════════════════════════════════════════════════════════════════════
class Case13_SingleActiveSession(TestCase):
    """
    FAIL SCENARIO: Two sessions both marked as active for the same school.
    Expected: When Session B is activated, Session A is automatically deactivated.
    """

    def setUp(self):
        self.school = make_school('School13')
        self.s1 = make_session(self.school, name='2080', active=True)

    def test_activating_second_session_deactivates_first(self):
        s2 = AcademicSession.objects.create(
            school=self.school, name='2081', is_active=True,
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
        )
        self.s1.refresh_from_db()
        self.assertFalse(self.s1.is_active,
                         "Session 2080 should have been deactivated when 2081 was activated")
        self.assertTrue(s2.is_active)
        s2.delete()

    def tearDown(self):
        self.s1.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 14: Subject deletion cascades StudentResult cleanup
# ══════════════════════════════════════════════════════════════════════════════
class Case14_SubjectDeletionCleansResults(TestCase):
    """
    FAIL SCENARIO: A subject is deleted after results are processed.
    Expected: post_delete signal deletes all StudentResult records for that class.
    """

    def setUp(self):
        self.school = make_school('School14')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.subject = make_subject(self.school, self.cls, code='ENV', name='Environment')
        self.exam = make_exam(self.school, self.session)
        ec = ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls)
        # Create a fake StudentResult
        self.sr = StudentResult.objects.create(
            school=self.school, exam=self.exam, session=self.session,
            student=self.student, is_pass=True, final_grade='B',
            overall_gpa=Decimal('2.80')
        )

    def test_subject_deletion_deletes_student_results(self):
        self.assertTrue(StudentResult.objects.filter(pk=self.sr.pk).exists())
        # Delete the subject — triggers post_delete signal
        self.subject.delete()
        # StudentResult for the class should be cleaned up
        self.assertFalse(
            StudentResult.objects.filter(student__class_obj=self.cls).exists(),
            "StudentResults should be deleted when subject is deleted"
        )

    def tearDown(self):
        # Clean up remaining objects
        try:
            self.exam.delete()
        except Exception:
            pass
        try:
            self.cls.delete()
        except Exception:
            pass
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 15: Student class transfer clears old marks and student results
# ══════════════════════════════════════════════════════════════════════════════
class Case15_StudentClassTransferClearsMarks(TestCase):
    """
    FAIL SCENARIO: A student is transferred from Class A to Class B.
    Expected: pre_save signal clears MarkEntries for old class subjects
    and StudentResult records, preventing stale results.
    """

    def setUp(self):
        self.school = make_school('School15')
        self.session = make_session(self.school)
        self.cls_a = make_class(self.school, self.session, name='Class 10', section='A')
        self.cls_b = make_class(self.school, self.session, name='Class 11', section='A')
        self.subject_a = make_subject(self.school, self.cls_a, code='SCI', name='Science')
        self.exam = make_exam(self.school, self.session)
        ExamClass.objects.create(exam=self.exam, class_obj=self.cls_a)
        self.student = make_student(self.school, self.cls_a, roll='10')
        # Create mark and result for the student in old class
        self.me = MarkEntry.objects.create(
            exam=self.exam, school=self.school,
            student=self.student, subject=self.subject_a,
            theory_obtained=Decimal('75')
        )
        self.result = StudentResult.objects.create(
            school=self.school, exam=self.exam, session=self.session,
            student=self.student, is_pass=True, final_grade='B+'
        )

    def test_class_transfer_removes_old_marks_and_results(self):
        # Transfer student to new class
        self.student.class_obj = self.cls_b
        self.student.save()

        # MarkEntry for old class subject should be deleted
        self.assertFalse(
            MarkEntry.objects.filter(pk=self.me.pk).exists(),
            "Old MarkEntry should be deleted after class transfer"
        )
        # StudentResult should also be deleted
        self.assertFalse(
            StudentResult.objects.filter(pk=self.result.pk).exists(),
            "StudentResult should be deleted after class transfer"
        )

    def tearDown(self):
        self.exam.delete()
        self.cls_a.delete()
        self.cls_b.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 16: GradingEngine — all-special-value entries yield no letter grade
# ══════════════════════════════════════════════════════════════════════════════
class Case16_GradingEngineSpecialValues(TestCase):
    """
    FAIL SCENARIO: Student is absent (special_value='AB') in all subjects.
    Expected: grade='NG', grade_point=None, is_pass=False.
    """

    def setUp(self):
        self.school = make_school('School16')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.subject = make_subject(self.school, self.cls, code='SCI2', name='Science2')
        self.exam = make_exam(self.school, self.session)
        ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls)

    def test_absent_student_gets_ng_grade(self):
        me = MarkEntry.objects.create(
            exam=self.exam, school=self.school,
            student=self.student, subject=self.subject,
            special_value=MarkEntry.SpecialValue.ABSENT
        )
        engine = GradingEngine(system='NEB')
        ms = self.subject.marking_structure
        result = engine.get_subject_result(me, ms)
        self.assertEqual(result['grade'], 'NG')
        self.assertIsNone(result['grade_point'])
        self.assertFalse(result['is_pass'])

    def tearDown(self):
        self.exam.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 17: GradingEngine — NON_CREDIT subjects excluded from GPA/pass-fail
# ══════════════════════════════════════════════════════════════════════════════
class Case17_NonCreditSubjectExcludedFromGPA(TestCase):
    """
    FAIL SCENARIO: A student fails a NON_CREDIT subject.
    Expected: Student overall is still PASS (non-credit doesn't affect pass/fail).
    """

    def setUp(self):
        self.school = make_school('School17')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.compulsory_subject = make_subject(self.school, self.cls, code='ENG2', name='English2')
        self.non_credit_subject = make_subject(
            self.school, self.cls, code='PE', name='Physical Education',
            subject_type='NON_CREDIT'
        )
        self.exam = make_exam(self.school, self.session)
        ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls)

    def test_failing_non_credit_does_not_fail_student(self):
        engine = GradingEngine(system='NEB')
        ms_compulsory = self.compulsory_subject.marking_structure
        ms_nc = self.non_credit_subject.marking_structure

        # Pass the compulsory subject
        me_pass = MarkEntry(
            exam=self.exam, school=self.school,
            student=self.student, subject=self.compulsory_subject,
            theory_obtained=Decimal('40')
        )
        # Fail the non-credit subject
        me_fail = MarkEntry(
            exam=self.exam, school=self.school,
            student=self.student, subject=self.non_credit_subject,
            theory_obtained=Decimal('10')  # Well below pass mark
        )

        result_pass = engine.get_subject_result(me_pass, ms_compulsory)
        result_fail = engine.get_subject_result(me_fail, ms_nc)

        # Build mock subject results as objects with .is_pass and .mark_entry.subject
        class MockSR:
            def __init__(self, me, is_pass):
                self.mark_entry = me
                self.is_pass = is_pass
                self.grade_point = Decimal('1.60')

        sr_pass = MockSR(me_pass, result_pass['is_pass'])
        sr_fail = MockSR(me_fail, result_fail['is_pass'])

        # Non-credit subject should not affect pass/fail
        is_pass, failed_subjects = engine.is_student_pass([sr_pass, sr_fail], [])
        self.assertTrue(is_pass,
                        f"Student should PASS even if non-credit subject fails. "
                        f"Failed: {failed_subjects}")
        self.assertNotIn('Physical Education', failed_subjects)

    def tearDown(self):
        self.exam.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 18: ResultProcessingService — missing mark entries auto-created as AB
# ══════════════════════════════════════════════════════════════════════════════
class Case18_MissingMarkEntriesAutoCreatedAsAB(TestCase):
    """
    FAIL SCENARIO: A student exists but has NO MarkEntry for a subject.
    Expected: ResultProcessingService auto-creates the entry as 'AB' (Absent).
    """

    def setUp(self):
        self.school = make_school('School18')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.subject = make_subject(self.school, self.cls, code='BIO', name='Biology')
        self.exam = make_exam(self.school, self.session)
        ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls)
        # Intentionally do NOT create any MarkEntry

    def test_missing_mark_entries_are_auto_created_as_absent(self):
        service = ResultProcessingService(self.exam)
        count = service.process(class_obj=self.cls)
        # Auto-created MarkEntry should exist and be AB
        me = MarkEntry.objects.filter(
            exam=self.exam, student=self.student, subject=self.subject
        ).first()
        self.assertIsNotNone(me, "MarkEntry should have been auto-created")
        self.assertEqual(me.special_value, 'AB',
                         f"Expected special_value='AB', got '{me.special_value}'")

    def tearDown(self):
        MarkEntry.objects.filter(exam=self.exam).delete()
        SubjectResult.objects.filter(school=self.school).delete()
        StudentResult.objects.filter(school=self.school).delete()
        self.exam.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CASE 19: calculate_ranks — failed students get no rank; GPA ties share rank
# ══════════════════════════════════════════════════════════════════════════════
class Case19_RankCalculation(TestCase):
    """
    FAIL SCENARIO: Mixed pass/fail students and tied GPAs.
    Expected: Failed → class_rank=None; identical GPA+marks → same rank; next rank skips.
    """

    def _make_sr(self, gpa, is_pass, marks):
        """Create a mock StudentResult-like object."""
        class FakeSR:
            pass
        sr = FakeSR()
        sr.overall_gpa = Decimal(str(gpa)) if is_pass else None
        sr.total_marks_obtained = Decimal(str(marks))
        sr.is_pass = is_pass
        sr.class_rank = None
        return sr

    def test_failed_student_gets_no_rank(self):
        results = [
            self._make_sr(3.2, True, 500),
            self._make_sr(None, False, 200),  # failed
        ]
        ranked = calculate_ranks(results)
        failed = [r for r in ranked if not r.is_pass]
        self.assertIsNone(failed[0].class_rank)

    def test_tied_gpa_and_marks_get_same_rank(self):
        results = [
            self._make_sr(3.2, True, 500),
            self._make_sr(3.2, True, 500),  # exact tie
            self._make_sr(2.8, True, 450),
        ]
        ranked = calculate_ranks(results)
        passed = [r for r in ranked if r.is_pass]
        ranks = [r.class_rank for r in passed]
        self.assertEqual(ranks[0], 1)
        self.assertEqual(ranks[1], 1, "Tied students should share rank 1")
        self.assertEqual(ranks[2], 3, "After tie at 1,1, next rank should be 3 (skip 2)")

    def test_all_passed_sequential_ranks(self):
        results = [
            self._make_sr(4.0, True, 600),
            self._make_sr(3.6, True, 550),
            self._make_sr(2.0, True, 400),
        ]
        ranked = calculate_ranks(results)
        passed = [r for r in ranked if r.is_pass]
        for i, r in enumerate(passed, 1):
            self.assertEqual(r.class_rank, i)


# ══════════════════════════════════════════════════════════════════════════════
# CASE 20: AJAX save_mark — locked exam returns 403; unlocking allows save
# ══════════════════════════════════════════════════════════════════════════════
class Case20_LockedExamAJAXSaveMark(TestCase):
    """
    FAIL SCENARIO: Mark entry is attempted via AJAX on a locked exam.
    Expected: 403 response from save_mark endpoint.
    Then after unlocking, the same request should succeed.
    """

    def setUp(self):
        self.school = make_school('School20')
        self.session = make_session(self.school)
        self.cls = make_class(self.school, self.session)
        self.subject = make_subject(self.school, self.cls, code='SOC', name='Social Studies')
        self.exam = make_exam(self.school, self.session)
        self.exam_class = ExamClass.objects.create(exam=self.exam, class_obj=self.cls)
        self.student = make_student(self.school, self.cls)
        self.user = make_user(self.school, 'admin20')
        self.client = Client()
        self.client.login(username='admin20', password='Pass@1234')

    def _post_mark(self):
        import json
        return self.client.post(
            '/marks/save/',
            data=json.dumps({
                'exam_id': self.exam.pk,
                'student_id': self.student.pk,
                'subject_id': self.subject.pk,
                'theory_obtained': '75',
                'internal_obtained': None,
                'special_value': None,
                'present_days': None,
                'total_days': None,
            }),
            content_type='application/json',
        )

    def test_locked_exam_returns_403(self):
        # Lock the exam class
        self.exam_class.is_locked = True
        self.exam_class.save()
        response = self._post_mark()
        self.assertEqual(response.status_code, 403,
                         f"Expected 403 for locked exam, got {response.status_code}: "
                         f"{response.content.decode()}")

    def test_unlocked_exam_allows_save(self):
        # Ensure exam class is unlocked
        self.exam_class.is_locked = False
        self.exam_class.save()
        response = self._post_mark()
        self.assertEqual(response.status_code, 200,
                         f"Expected 200 for unlocked exam, got {response.status_code}: "
                         f"{response.content.decode()}")
        import json
        data = json.loads(response.content)
        self.assertEqual(data.get('status'), 'saved')

    def tearDown(self):
        MarkEntry.objects.filter(exam=self.exam).delete()
        self.exam.delete()
        self.user.delete()
        self.cls.delete()
        self.session.delete()
        self.school.delete()


# ── Runner ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import unittest

    print("=" * 70)
    print("  RESULT MANAGEMENT — 20 REAL-WORLD FAILURE CASE TEST SUITE")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    cases = [
        Case01_DisabledAccountLogin,
        Case02_ExpiredSubscriptionLogin,
        Case03_SubscriptionBoundary,
        Case04_StudentInvalidNepaliDate,
        Case05_ExamClassCrossSession,
        Case06_MarkEntryInactiveStudent,
        Case07_MarkEntryExceedsFullMarks,
        Case08_InternalMarksNoPractical,
        Case09_AttendanceExceedsTotalDays,
        Case10_ReduceFullMarksBelowExistingEntry,
        Case11_DuplicateRollNumber,
        Case12_CrossSchoolTeacherAssignment,
        Case13_SingleActiveSession,
        Case14_SubjectDeletionCleansResults,
        Case15_StudentClassTransferClearsMarks,
        Case16_GradingEngineSpecialValues,
        Case17_NonCreditSubjectExcludedFromGPA,
        Case18_MissingMarkEntriesAutoCreatedAsAB,
        Case19_RankCalculation,
        Case20_LockedExamAJAXSaveMark,
    ]

    for case in cases:
        suite.addTests(loader.loadTestsFromTestCase(case))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed
    print(f"  TOTAL: {total}  |  PASSED: {passed}  |  FAILED: {failed}")
    print("=" * 70)

    sys.exit(1 if failed > 0 else 0)
