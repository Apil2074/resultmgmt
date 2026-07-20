"""
Core Grading Engine — supports SEE, NEB, and Custom grading systems.
Fully compliant with NEB Letter Grading Directive 2078 BS.
"""
from decimal import Decimal, ROUND_HALF_UP


# ─────────────────────────────────────────────────────────────
# NEB Grading Scale (National Examinations Board — Nepal, +2 Level)
# ─────────────────────────────────────────────────────────────
NEB_GRADE_TABLE = [
    (Decimal('90.0'), Decimal('100.0'), 'A+', Decimal('4.0')),
    (Decimal('80.0'), Decimal('90.0'),  'A',  Decimal('3.6')),
    (Decimal('70.0'), Decimal('80.0'),  'B+', Decimal('3.2')),
    (Decimal('60.0'), Decimal('70.0'),  'B',  Decimal('2.8')),
    (Decimal('50.0'), Decimal('60.0'),  'C+', Decimal('2.4')),
    (Decimal('40.0'), Decimal('50.0'),  'C',  Decimal('2.0')),
    (Decimal('35.0'), Decimal('40.0'),  'D',  Decimal('1.6')),
    (Decimal('0.0'),  Decimal('35.0'),  'NG', Decimal('0.0')),  # Not Graded
]

GRADE_TABLES = {
    'NEB': NEB_GRADE_TABLE,
}


def percentage_to_grade_info(percentage, system='NEB', custom_table=None):
    """
    Convert a percentage to (grade, grade_point) tuple using precise Decimal logic.
    Returns ('NG', 0.0) if not graded or missing.
    """
    if percentage is None:
        return ('NG', Decimal('0.0'))

    table = custom_table or GRADE_TABLES.get(system, NEB_GRADE_TABLE)
    
    # Clamp percentage between 0.0 and 100.0 to prevent edge-case bugs
    pct = max(Decimal('0.0'), min(Decimal(str(percentage)), Decimal('100.0')))

    # Find matching bracket
    for min_pct, max_pct, grade, gp in table:
        if pct >= min_pct:
            return (grade, gp if isinstance(gp, Decimal) else Decimal(str(gp)))

    # Fallback to the lowest threshold
    lowest = table[-1]
    return (lowest[2], Decimal(str(lowest[3])))


def marks_to_percentage(obtained, full_marks):
    """Convert obtained/full marks to a Decimal percentage safely."""
    if not full_marks or Decimal(str(full_marks)) <= Decimal('0.0'):
        return Decimal('0.0')
    
    obtained_val = Decimal(str(obtained)) if obtained is not None else Decimal('0.0')
    return (obtained_val / Decimal(str(full_marks))) * Decimal('100.0')


def get_neb_final_grade(gpa):
    """
    Map a calculated Subject AVG GPA or Overall GPA to the official NEB Final Grade Letter.
    Uses strict > operators to map ranges cleanly without magic '+0.01' offsets.
    """
    if gpa is None or gpa < Decimal('1.60'): return 'NG'
    elif gpa > Decimal('3.60'): return 'A+'
    elif gpa > Decimal('3.20'): return 'A'
    elif gpa > Decimal('2.80'): return 'B+'
    elif gpa > Decimal('2.40'): return 'B'
    elif gpa > Decimal('2.00'): return 'C+'
    elif gpa > Decimal('1.60'): return 'C'
    elif gpa == Decimal('1.60'): return 'D'
    
    return 'NG'


class GradingEngine:
    """
    Main grading engine — given a school's grading system,
    calculates grade points, GPAs, and final results.
    """

    def __init__(self, system='NEB', custom_table=None):
        self.system = system
        self.custom_table = custom_table

    def get_subject_result(self, mark_entry):
        """
        Calculate theory, internal, combined GPA, and final letter grade for a single subject.
        """
        result = {
            'grade_point': Decimal('0.00'),
            'grade': 'NG',
            'gpa': Decimal('0.00'),
            'theory_grade_point': Decimal('0.00'),
            'theory_grade': 'NG',
            'internal_grade_point': Decimal('0.00'),
            'internal_grade': 'NG',
            'is_pass': False,
            'remarks': '',
            'mark_entry': mark_entry, 
        }

        if getattr(mark_entry, 'special_value', None):
            result['remarks'] = mark_entry.get_special_value_display()
            return result

        subject = mark_entry.subject

        # 1. Theory Evaluation (35% Threshold Rule)
        pass_threshold_theory = Decimal('35.0')
        theory_pass = False

        if getattr(mark_entry, 'theory_obtained', None) is not None:
            theory_pct = marks_to_percentage(mark_entry.theory_obtained, subject.theory_full_marks)
            t_grade, t_gp = percentage_to_grade_info(theory_pct, self.system, self.custom_table)
            
            result['theory_grade'] = t_grade
            result['theory_grade_point'] = t_gp
            theory_pass = theory_pct >= pass_threshold_theory

        # 2. Internal/Practical Evaluation (40% Threshold Rule)
        pass_threshold_internal = Decimal('40.0')
        internal_pass = True

        if getattr(subject, 'has_practical', False):
            if getattr(mark_entry, 'internal_obtained', None) is not None:
                internal_pct = marks_to_percentage(mark_entry.internal_obtained, subject.practical_full_marks)
                i_grade, i_gp = percentage_to_grade_info(internal_pct, self.system, self.custom_table)
                
                result['internal_grade'] = i_grade
                result['internal_grade_point'] = i_gp
                internal_pass = internal_pct >= pass_threshold_internal
            else:
                internal_pass = False

        # Subject Pass Verification
        is_pass = theory_pass and internal_pass
        result['is_pass'] = is_pass

        # 3. Weighted Grade Point (WGP) Calculation
        ch_t = Decimal(str(getattr(subject, 'theory_credit_hour', '0') or '0'))
        ch_p = Decimal(str(getattr(subject, 'practical_credit_hour', '0') or '0')) if getattr(subject, 'has_practical', False) else Decimal('0')
        total_ch = ch_t + ch_p

        if total_ch > 0 and is_pass:
            theory_wgp = result['theory_grade_point'] * ch_t
            internal_wgp = result['internal_grade_point'] * ch_p

            # Calculate GPA and round standard arithmetic style (ROUND_HALF_UP)
            gp = (theory_wgp + internal_wgp) / total_ch
            gp = gp.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Map to Final Grade
            if self.custom_table:
                sorted_custom = sorted(self.custom_table, key=lambda x: -x[3])
                grade = 'NG'
                for _, _, g_name, g_point in sorted_custom:
                    if gp >= Decimal(str(g_point)):
                        grade = g_name
                        break
            else:
                grade = get_neb_final_grade(gp)

            result['grade'] = grade
            result['grade_point'] = gp
            result['gpa'] = gp
        else:
            result['grade'] = 'NG'
            result['grade_point'] = Decimal('0.00')
            result['gpa'] = Decimal('0.00')

        return result

    def calculate_student_gpa(self, subject_results):
        """
        Calculate overall GPA from a list of SubjectResult dicts/objects.
        Non-credit subjects (affects_gpa=False) are entirely skipped.
        If a student fails a core credit subject, the final GPA becomes NG.
        """
        total_credit_gpa = Decimal('0')
        total_credit_hours = Decimal('0')

        for sr in subject_results:
            # Safely handle both dicts (from views) and objects (from DB models)
            mark_entry = sr['mark_entry'] if isinstance(sr, dict) else sr.mark_entry
            is_pass = sr['is_pass'] if isinstance(sr, dict) else sr.is_pass
            grade_point = sr['grade_point'] if isinstance(sr, dict) else sr.grade_point
            
            subject = mark_entry.subject

            # Skip non-credit subjects for overall GPA 
            if getattr(subject, 'affects_gpa', False):
                
                # If they failed a credit subject, overall GPA is instantly NG
                if not is_pass:
                    return Decimal('0.00'), 'NG'

                # Dynamically calculate credit hours mathematically (immune to database typos)
                ch_t = Decimal(str(getattr(subject, 'theory_credit_hour', '0') or '0'))
                ch_p = Decimal(str(getattr(subject, 'practical_credit_hour', '0') or '0')) if getattr(subject, 'has_practical', False) else Decimal('0')
                ch = ch_t + ch_p
                
                total_credit_gpa += (grade_point * ch)
                total_credit_hours += ch

        if total_credit_hours == Decimal('0'):
            return None, '—'

        overall_gpa = (total_credit_gpa / total_credit_hours).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        if self.custom_table:
            sorted_custom = sorted(self.custom_table, key=lambda x: -x[3])
            final_grade = 'NG'
            for _, _, g_name, g_point in sorted_custom:
                if overall_gpa >= Decimal(str(g_point)):
                    final_grade = g_name
                    break
        else:
            final_grade = get_neb_final_grade(overall_gpa)

        return overall_gpa, final_grade

    def is_student_pass(self, subject_results):
        """
        Checks if a student passes. 
        Only checks subjects where affects_pass_fail=True.
        Non-credit/optional failures are ignored completely.
        """
        failed = []
        for sr in subject_results:
            mark_entry = sr['mark_entry'] if isinstance(sr, dict) else sr.mark_entry
            is_pass = sr['is_pass'] if isinstance(sr, dict) else sr.is_pass
            subject = mark_entry.subject

            if getattr(subject, 'affects_pass_fail', False) and not is_pass:
                failed.append(subject.name)
                
        return len(failed) == 0, failed


def calculate_ranks(student_results):
    """
    Assign class_rank to a list of StudentResult objects.
    Uses 'Dense Ranking' (e.g., 1, 1, 2, 2, 3) natively with Decimals to prevent precision bugs.
    Failed students receive no rank.
    """
    passed_students = [r for r in student_results if getattr(r, 'is_pass', False)]
    failed_students = [r for r in student_results if not getattr(r, 'is_pass', False)]

    # Sort descending by GPA, then by total marks (pure Decimal comparison)
    sorted_passed = sorted(
        passed_students,
        key=lambda r: (
            -(getattr(r, 'overall_gpa', None) or Decimal('0.00')),
            -(Decimal(str(getattr(r, 'total_marks_obtained', '0') or '0')))
        )
    )

    rank = 0
    prev_gpa = None
    prev_marks = None

    for sr in sorted_passed:
        gpa = getattr(sr, 'overall_gpa', None) or Decimal('0.00')
        marks = Decimal(str(getattr(sr, 'total_marks_obtained', '0') or '0'))

        # Increment rank only when scores change (Dense Ranking logic)
        if gpa != prev_gpa or marks != prev_marks:
            rank += 1 
            
        sr.class_rank = rank
        
        prev_gpa = gpa
        prev_marks = marks

    for sr in failed_students:
        sr.class_rank = None

    return sorted_passed + failed_students
