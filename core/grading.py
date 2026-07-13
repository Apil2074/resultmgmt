"""
Core Grading Engine — supports SEE, NEB, and Custom grading systems
"""
from decimal import Decimal


# ─────────────────────────────────────────────────────────────
# NEB Grading (National Examinations Board — Nepal, +2 Level)
# ─────────────────────────────────────────────────────────────
NEB_GRADE_TABLE = [
    (90, 100, 'A+',  4.0),
    (80,  90, 'A',   3.6),
    (70,  80, 'B+',  3.2),
    (60,  70, 'B',   2.8),
    (50,  60, 'C+',  2.4),
    (40,  50, 'C',   2.0),
    (35,  40, 'D',   1.6),
    ( 0,  35, 'NG',  0.0),  # Not Graded
]

GRADE_TABLES = {
    'NEB': NEB_GRADE_TABLE,
}

PASS_GRADE_POINTS = {
    'NEB': Decimal('1.6'),   # D or above
}


def percentage_to_grade_info(percentage, system='NEB', custom_table=None):
    """
    Convert a percentage to (grade, grade_point) tuple.
    Returns ('NG', 0.0) if not graded / special case.
    """
    if percentage is None:
        return ('NG', Decimal('0.0'))

    table = custom_table or GRADE_TABLES.get(system, NEB_GRADE_TABLE)
    pct = float(percentage)
    if pct > 100.0:
        pct = 100.0

    for min_pct, max_pct, grade, gp in table:
        if min_pct <= pct <= max_pct:
            return (grade, Decimal(str(gp)))

    # Below the lowest threshold
    lowest = table[-1]
    return (lowest[2], Decimal(str(lowest[3])))


def marks_to_percentage(obtained, full_marks):
    """Convert obtained/full marks to percentage."""
    if full_marks <= 0:
        return Decimal('0.0')
    return Decimal(str(obtained)) / Decimal(str(full_marks)) * 100


class GradingEngine:
    """
    Main grading engine — given a school's grading system,
    calculates grade points, GPAs, and final results.
    """

    def __init__(self, system='NEB', custom_table=None):
        self.system = system
        self.custom_table = custom_table

    def get_subject_result(self, mark_entry, marking_structure):
        """
        Calculate grade_point, grade, gpa, is_pass for a single subject mark entry.
        Returns a dict with all computed values.
        """
        from apps.marks.models import MarkEntry

        result = {
            'grade_point': None,
            'grade': 'NG',
            'gpa': None,
            'theory_grade_point': None,
            'theory_grade': '',
            'internal_grade_point': None,
            'internal_grade': '',
            'is_pass': False,
            'remarks': '',
        }

        # Handle special values
        if mark_entry.special_value:
            result['remarks'] = mark_entry.get_special_value_display()
            return result

        ms = marking_structure
        subject = mark_entry.subject

        # Theory computation
        theory_pct = None
        theory_gp = Decimal('0.0')
        theory_pass = True
        pass_threshold_theory = 35.0

        if ms.has_theory:
            if mark_entry.theory_obtained is not None:
                theory_pct = marks_to_percentage(
                    mark_entry.theory_obtained, ms.theory_full_marks
                )
                t_grade, t_gp = percentage_to_grade_info(theory_pct, self.system, self.custom_table)
                result['theory_grade'] = t_grade
                result['theory_grade_point'] = t_gp
                theory_gp = t_gp
                theory_pass = float(theory_pct) >= pass_threshold_theory
            else:
                theory_pass = False

        # Internal/Practical computation
        internal_pct = None
        internal_gp = Decimal('0.0')
        internal_pass = True
        pass_threshold_internal = 40.0

        if subject.has_practical:
            if mark_entry.internal_obtained is not None:
                internal_pct = marks_to_percentage(
                    mark_entry.internal_obtained, ms.internal_full_marks
                )
                i_grade, i_gp = percentage_to_grade_info(internal_pct, self.system, self.custom_table)
                result['internal_grade'] = i_grade
                result['internal_grade_point'] = i_gp
                internal_gp = i_gp
                internal_pass = float(internal_pct) >= pass_threshold_internal
            else:
                internal_pass = False

        # Combined computation
        ch_t = Decimal(str(subject.theory_credit_hour))
        ch_p = Decimal(str(subject.practical_credit_hour or '0')) if subject.has_practical else Decimal('0')
        total_ch = ch_t + ch_p

        is_pass = theory_pass and internal_pass
        result['is_pass'] = is_pass

        if total_ch > 0:
            if is_pass:
                # WGP Calculation
                theory_wgp = theory_gp * ch_t
                internal_wgp = internal_gp * ch_p
                
                gp = (theory_wgp + internal_wgp) / total_ch
                gp = gp.quantize(Decimal('0.01'))
                
                # Subject Final Letter Grade Mapping
                grade = 'NG'
                fgp = float(gp)
                if self.custom_table:
                    sorted_custom = sorted(self.custom_table, key=lambda x: -x[3])
                    for min_pct, max_pct, g_name, g_point in sorted_custom:
                        if gp >= Decimal(str(g_point)):
                            grade = g_name
                            break
                else:
                    if fgp >= 3.61: grade = 'A+'
                    elif fgp >= 3.21: grade = 'A'
                    elif fgp >= 2.81: grade = 'B+'
                    elif fgp >= 2.41: grade = 'B'
                    elif fgp >= 2.01: grade = 'C+'
                    elif fgp >= 1.61: grade = 'C'
                    elif fgp >= 1.60: grade = 'D'
                
                result['grade'] = grade
                result['grade_point'] = gp
                result['gpa'] = gp
            else:
                result['grade'] = 'NG'
                result['grade_point'] = Decimal('0.00')
                result['gpa'] = Decimal('0.00')

        return result

    def calculate_student_gpa(self, subject_results, subjects):
        """
        Calculate overall GPA from a list of SubjectResult objects.
        Non-credit subjects are excluded from GPA.
        Returns (overall_gpa, final_grade).
        """
        from apps.subjects.models import Subject

        total_credit_gpa = Decimal('0')
        total_credit_hours = Decimal('0')

        for sr in subject_results:
            subject = sr.mark_entry.subject
            if subject.affects_gpa and sr.grade_point is not None:
                ch = Decimal(str(subject.credit_hour))
                total_credit_gpa += sr.grade_point * ch
                total_credit_hours += ch

        if total_credit_hours == 0:
            return None, '—'

        overall_gpa = (total_credit_gpa / total_credit_hours).quantize(Decimal('0.01'))
        
        final_grade = 'NG'
        fgp = float(overall_gpa)
        if self.custom_table:
            sorted_custom = sorted(self.custom_table, key=lambda x: -x[3])
            for min_pct, max_pct, g_name, g_point in sorted_custom:
                if overall_gpa >= Decimal(str(g_point)):
                    final_grade = g_name
                    break
        else:
            if fgp >= 3.61: final_grade = 'A+'
            elif fgp >= 3.21: final_grade = 'A'
            elif fgp >= 2.81: final_grade = 'B+'
            elif fgp >= 2.41: final_grade = 'B'
            elif fgp >= 2.01: final_grade = 'C+'
            elif fgp >= 1.61: final_grade = 'C'
            elif fgp >= 1.60: final_grade = 'D'

        return overall_gpa, final_grade

    def is_student_pass(self, subject_results, subjects):
        """
        Student passes only if they pass all compulsory and optional subjects.
        Non-credit subjects don't affect pass/fail.
        """
        failed = []
        for sr in subject_results:
            subject = sr.mark_entry.subject
            if subject.affects_pass_fail and not sr.is_pass:
                failed.append(subject.name)
        return len(failed) == 0, failed


def calculate_ranks(student_results):
    """
    Assign class_rank to a queryset of StudentResult objects.
    Only passed students are ranked. Failed students get no rank (NG).
    Handles ties (same GPA → same rank; next rank skips).
    Returns the updated list.
    """
    # Separate into passed and failed
    passed_students = [r for r in student_results if r.is_pass]
    failed_students = [r for r in student_results if not r.is_pass]

    # Sort only passed students
    sorted_passed = sorted(
        passed_students,
        key=lambda r: (
            -(float(r.overall_gpa or 0)),
            float(r.total_marks_obtained or 0) * -1
        )
    )

    rank = 0
    prev_gpa = None
    prev_marks = None

    for idx, sr in enumerate(sorted_passed, 1):
        gpa = float(sr.overall_gpa or 0)
        marks = float(sr.total_marks_obtained or 0)
        
        if gpa == prev_gpa and marks == prev_marks:
            sr.class_rank = rank
        else:
            rank = idx
            sr.class_rank = rank
            
        prev_gpa = gpa
        prev_marks = marks

    # Assign no rank to failed students
    for sr in failed_students:
        sr.class_rank = None

    return sorted_passed + failed_students
