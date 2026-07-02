"""
Result Processing Service — orchestrates full result calculation for an exam
"""
from decimal import Decimal
from django.db import transaction
from apps.marks.models import MarkEntry
from apps.results.models import SubjectResult, StudentResult
from apps.subjects.models import Subject
from core.grading import GradingEngine, calculate_ranks


class ResultProcessingService:
    """
    Processes all marks for an exam and computes:
    - Subject-level grades/GPA
    - Student-level overall GPA, final grade, pass/fail, rank
    """

    def __init__(self, exam):
        self.exam = exam
        self.school = exam.school
        self.engine = GradingEngine(system=self.school.grading_system)

    @transaction.atomic
    def process(self, class_obj=None):
        """Run full result processing for the exam or a specific class."""
        # Clear existing results
        subject_filter = {'mark_entry__exam': self.exam}
        student_filter = {'exam': self.exam}
        mark_filter = {'exam': self.exam, 'school': self.school}

        if class_obj:
            subject_filter['mark_entry__student__class_obj'] = class_obj
            student_filter['student__class_obj'] = class_obj
            mark_filter['student__class_obj'] = class_obj

        SubjectResult.objects.filter(**subject_filter).delete()
        StudentResult.objects.filter(**student_filter).delete()

        from apps.students.models import Student
        if class_obj:
            students_qs = Student.objects.filter(class_obj=class_obj, school=self.school, is_active=True)
        else:
            students_qs = Student.objects.filter(school=self.school, is_active=True)

        student_map = {s.id: s for s in students_qs}
        student_entries = {s.id: [] for s in students_qs}

        # Get all mark entries grouped by student
        all_entries = MarkEntry.objects.filter(**mark_filter).select_related(
            'student', 'subject', 'subject__marking_structure'
        )

        # Group by student
        for entry in all_entries:
            sid = entry.student_id
            if sid not in student_entries:
                student_entries[sid] = []
            student_entries[sid].append(entry)

        student_results = []
        all_subject_results = []

        for student_id, entries in student_entries.items():
            subject_results = []

            for entry in entries:
                try:
                    ms = entry.subject.marking_structure
                except Exception:
                    continue

                computed = self.engine.get_subject_result(entry, ms)

                sr = SubjectResult(
                    mark_entry=entry,
                    school=self.school,
                    session=self.exam.session,
                    grade_point=computed['grade_point'],
                    grade=computed['grade'],
                    gpa=computed['gpa'],
                    theory_grade_point=computed['theory_grade_point'],
                    theory_grade=computed['theory_grade'],
                    internal_grade_point=computed['internal_grade_point'],
                    internal_grade=computed['internal_grade'],
                    is_pass=computed['is_pass'],
                    remarks=computed['remarks'],
                )
                subject_results.append(sr)
                all_subject_results.append(sr)

            # Calculate pass/fail status
            is_pass, failed_subjects = self.engine.is_student_pass(
                subject_results, []
            )

            # Calculate student-level result
            if is_pass:
                overall_gpa, final_grade = self.engine.calculate_student_gpa(
                    subject_results, []
                )
            else:
                overall_gpa = None
                final_grade = 'NG'

            # Total marks
            total_obtained = sum(
                float(e.total_obtained or 0) for e in entries if not e.is_special
            )
            total_full = sum(
                e.subject.marking_structure.total_full_marks for e in entries
                if hasattr(e.subject, 'marking_structure')
            )
            total_credit_hours = sum(
                float(e.subject.credit_hour) for e in entries
                if e.subject.affects_gpa
            )
            percentage = (
                Decimal(str(total_obtained)) / Decimal(str(total_full)) * 100
                if total_full > 0 else Decimal('0')
            )

            student = student_map.get(student_id)
            if not student:
                student = entries[0].student if entries else None
            if not student:
                continue
            sr_obj = StudentResult(
                school=self.school,
                exam=self.exam,
                session=self.exam.session,
                student=student,
                total_credit_hours=Decimal(str(total_credit_hours)),
                total_marks_obtained=Decimal(str(total_obtained)),
                total_full_marks=total_full,
                percentage=percentage.quantize(Decimal('0.01')),
                overall_gpa=overall_gpa,
                final_grade=final_grade,
                is_pass=is_pass,
                failed_subjects=failed_subjects,
            )
            student_results.append(sr_obj)

        # Bulk Create Results
        SubjectResult.objects.bulk_create(all_subject_results, batch_size=1000)
        StudentResult.objects.bulk_create(student_results, batch_size=500)

        # Assign ranks using bulk_update
        # Fetch back to ensure we have PKs for bulk_update
        if class_obj:
            classes_to_rank = [class_obj]
        else:
            # If no class specified, we should rank each class separately
            from apps.classes.models import Class
            class_ids = set(StudentResult.objects.filter(exam=self.exam).values_list('student__class_obj_id', flat=True))
            classes_to_rank = Class.objects.filter(id__in=class_ids)

        for c_obj in classes_to_rank:
            saved_student_results = list(StudentResult.objects.filter(
                exam=self.exam, student__class_obj=c_obj
            ).select_related('student'))
            ranked = calculate_ranks(saved_student_results)
            StudentResult.objects.bulk_update(ranked, ['class_rank'], batch_size=500)

        return len(student_results)
