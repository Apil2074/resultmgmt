"""
Exams App - Services for Exam operations
"""
from decimal import Decimal
from django.db import transaction
from apps.marks.models import MarkEntry
from apps.exams.models import ExamAggregationRule, ExamClass
from apps.results.services import ResultProcessingService

class ExamAggregationService:
    def __init__(self, aggregate_exam):
        self.aggregate_exam = aggregate_exam
        self.school = aggregate_exam.school

    @transaction.atomic
    def generate_aggregate_marks(self):
        """
        Generates MarkEntry records for the aggregate_exam based on the 
        weights defined in ExamAggregationRule.
        """
        if not self.aggregate_exam.is_aggregate:
            raise ValueError("This is not an aggregate exam.")

        rules = list(ExamAggregationRule.objects.filter(aggregate_exam=self.aggregate_exam))
        if not rules:
            return 0  # No rules defined

        # 1. Clear existing marks for the aggregate exam
        MarkEntry.objects.filter(exam=self.aggregate_exam).delete()
        
        # 2. Get the students that belong to the classes in this aggregate exam
        allowed_class_ids = ExamClass.objects.filter(exam=self.aggregate_exam).values_list('class_obj_id', flat=True)
        from apps.students.models import Student
        students = Student.objects.filter(class_obj_id__in=allowed_class_ids, school=self.school, is_active=True)
        
        # We need all mark entries from all source exams for these students
        source_exam_ids = [rule.source_exam_id for rule in rules]
        rule_map = {rule.source_exam_id: rule.weight_percentage for rule in rules}
        
        source_marks = MarkEntry.objects.filter(
            exam_id__in=source_exam_ids,
            student__in=students,
            school=self.school
        ).select_related('subject')

        # Group marks by (student_id, subject_id)
        # student_subject_marks[(student_id, subject_id)] = { exam_id: MarkEntry }
        student_subject_marks = {}
        
        for mark in source_marks:
            key = (mark.student_id, mark.subject_id)
            if key not in student_subject_marks:
                student_subject_marks[key] = {}
            student_subject_marks[key][mark.exam_id] = mark

        new_marks = []
        
        # 3. Calculate new marks based on weights
        for (student_id, subject_id), exam_marks in student_subject_marks.items():
            total_theory = Decimal('0')
            total_internal = Decimal('0')
            is_absent = True
            
            for source_exam_id, weight in rule_map.items():
                mark = exam_marks.get(source_exam_id)
                if not mark:
                    continue
                
                # If they were absent for a source exam, we add 0 marks for that weight.
                # If they were present in AT LEAST ONE source exam, they are not completely absent.
                if not mark.is_special:
                    is_absent = False
                    
                    if mark.theory_obtained is not None:
                        total_theory += (mark.theory_obtained * weight) / 100
                    
                    if mark.internal_obtained is not None:
                        total_internal += (mark.internal_obtained * weight) / 100

            if is_absent:
                new_marks.append(MarkEntry(
                    exam=self.aggregate_exam,
                    school=self.school,
                    session=self.aggregate_exam.session,
                    student_id=student_id,
                    subject_id=subject_id,
                    special_value=MarkEntry.SpecialValue.ABSENT
                ))
            else:
                new_marks.append(MarkEntry(
                    exam=self.aggregate_exam,
                    school=self.school,
                    session=self.aggregate_exam.session,
                    student_id=student_id,
                    subject_id=subject_id,
                    theory_obtained=total_theory.quantize(Decimal('0.01')),
                    internal_obtained=total_internal.quantize(Decimal('0.01')),
                ))

        # 4. Bulk create
        if new_marks:
            MarkEntry.objects.bulk_create(new_marks, batch_size=1000)

        # 5. Process results
        processor = ResultProcessingService(self.aggregate_exam)
        processor.process()

        return len(new_marks)
