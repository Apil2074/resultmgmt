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
        
        # Load custom scale if defined in database
        from apps.results.models import GradeScale
        custom_table = None
        scale = GradeScale.objects.filter(school=self.school).first()
        if scale:
            entries = list(scale.entries.all().order_by('-min_percentage'))
            if entries:
                custom_table = []
                for e in entries:
                    custom_table.append((
                        float(e.min_percentage),
                        float(e.max_percentage),
                        e.grade,
                        float(e.grade_point)
                    ))
        
        self.engine = GradingEngine(system='NEB', custom_table=custom_table)

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

        from apps.exams.models import ExamClass
        allowed_class_ids = ExamClass.objects.filter(exam=self.exam).values_list('class_obj_id', flat=True)

        from apps.students.models import Student
        if class_obj:
            students_qs = Student.objects.filter(class_obj=class_obj, school=self.school, is_active=True)
        else:
            students_qs = Student.objects.filter(class_obj_id__in=allowed_class_ids, school=self.school, is_active=True)

        student_map = {s.id: s for s in students_qs}
        student_entries = {s.id: [] for s in students_qs}

        # Get all mark entries grouped by student
        all_entries = MarkEntry.objects.filter(**mark_filter).select_related(
            'student', 'subject', 
        ).order_by('student_id').iterator(chunk_size=1000)

        from apps.subjects.models import Subject, StudentSubjectEnrollment
        if class_obj:
            subjects = list(Subject.objects.filter(class_obj=class_obj, school=self.school))
        else:
            subjects = list(Subject.objects.filter(class_obj_id__in=allowed_class_ids, school=self.school))

        optional_enrollments = set(
            StudentSubjectEnrollment.objects.filter(student__in=students_qs)
            .values_list('student_id', 'subject_id')
        )
        
        existing_mark_entries = set(MarkEntry.objects.filter(**mark_filter).values_list('student_id', 'subject_id'))
        
        missing_entries = []
        for student in students_qs:
            for subject in subjects:
                if subject.class_obj_id != student.class_obj_id:
                    continue
                if subject.subject_type == Subject.SubjectType.OPTIONAL:
                    if (student.id, subject.id) not in optional_enrollments:
                        continue
                if (student.id, subject.id) not in existing_mark_entries:
                    missing_entries.append(MarkEntry(
                        exam=self.exam,
                        school=self.school,
                        session=self.exam.session,
                        student=student,
                        subject=subject,
                        special_value='AB'
                    ))
                    
        if missing_entries:
            MarkEntry.objects.bulk_create(missing_entries, batch_size=1000)
            # Re-fetch after creation
            all_entries = MarkEntry.objects.filter(**mark_filter).select_related(
                'student', 'subject', 
            ).order_by('student_id').iterator(chunk_size=1000)

        total_processed_students = 0

        student_results = []
        all_subject_results = []

        def process_student_entries(entries):
            if not entries: return
            subject_results = []
            for entry in entries:
                if entry.subject.subject_type == Subject.SubjectType.OPTIONAL:
                    if (entry.student_id, entry.subject_id) not in optional_enrollments:
                        continue

                computed = self.engine.get_subject_result(entry)

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
            is_pass, failed_subjects = self.engine.is_student_pass(subject_results)

            if is_pass:
                overall_gpa, final_grade = self.engine.calculate_student_gpa(subject_results)
            else:
                overall_gpa = None
                final_grade = 'NG'

            # Total marks
            total_obtained = sum(float(e.total_obtained or 0) for e in entries if not e.is_special)
            total_full = sum((e.subject.theory_full_marks + (e.subject.practical_full_marks or 0)) for e in entries if e.subject)
            total_credit_hours = sum(float(e.subject.credit_hour) for e in entries if e.subject.affects_gpa)
            percentage = Decimal(str(total_obtained)) / Decimal(str(total_full)) * 100 if total_full > 0 else Decimal('0')

            student = entries[0].student
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
            
            # Batch save to DB to avoid OOM
            if len(student_results) >= 200:
                SubjectResult.objects.bulk_create(all_subject_results, batch_size=1000)
                StudentResult.objects.bulk_create(student_results, batch_size=1000)
                nonlocal total_processed_students
                total_processed_students += len(student_results)
                student_results.clear()
                all_subject_results.clear()

        current_student_id = None
        current_entries = []

        for entry in all_entries:
            if current_student_id != entry.student_id:
                process_student_entries(current_entries)
                current_entries = []
                current_student_id = entry.student_id
            current_entries.append(entry)

        # Process the last student
        process_student_entries(current_entries)

        # Bulk Create remaining results
        if student_results:
            SubjectResult.objects.bulk_create(all_subject_results, batch_size=1000)
            StudentResult.objects.bulk_create(student_results, batch_size=1000)
            total_processed_students += len(student_results)

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

        return total_processed_students
