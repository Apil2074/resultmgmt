import random
from apps.exams.models import Exam
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.marks.models import MarkEntry
from apps.classes.models import Class
from django.db import transaction
import decimal

def run():
    exam = Exam.objects.get(id=10) # FIRST TERMINAL
    school = exam.school
    session = exam.session
    
    # Get all students
    students = Student.objects.filter(school=school, is_active=True)
    print(f"Found {students.count()} active students.")
    
    # We need to know which subjects apply to which students.
    # Usually subjects are tied to classes. Let's see.
    # The MarkEntry takes student, subject, exam, school, session.
    
    # Delete existing marks for this exam to avoid unique constraint errors if re-run
    MarkEntry.objects.filter(exam=exam).delete()
    print("Cleared existing marks for this exam.")
    
    entries = []
    for student in students:
        # Get subjects for this student's class
        # Look at Subject model to see if it has 'classes' many-to-many or ForeignKey
        # Or look at student.current_class.subjects
        cls = student.current_class
        subjects = Subject.objects.filter(school=school, classes=cls)
        
        for subject in subjects:
            struct = subject.marking_structure
            
            # Generate random theory mark (between 30% and 100% of full marks)
            theory_max = float(struct.theory_full_marks)
            if theory_max > 0:
                theory_obt = round(random.uniform(theory_max * 0.3, theory_max), 2)
            else:
                theory_obt = None
                
            # Generate random internal mark
            if struct.has_internal:
                int_max = float(struct.internal_full_marks)
                int_obt = round(random.uniform(int_max * 0.5, int_max), 2)
            else:
                int_obt = None
                
            entry = MarkEntry(
                school=school,
                exam=exam,
                session=session,
                student=student,
                subject=subject,
                theory_obtained=theory_obt,
                internal_obtained=int_obt,
                present_days=random.randint(45, 50),
                total_days=50,
            )
            # validate
            # entry.clean()
            entries.append(entry)
            
    print(f"Creating {len(entries)} mark entries...")
    MarkEntry.objects.bulk_create(entries, batch_size=500)
    print("Done!")

if __name__ == '__main__':
    run()
