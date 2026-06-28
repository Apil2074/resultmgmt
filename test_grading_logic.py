from decimal import Decimal
from core.grading import GradingEngine

class MockMarkingStructure:
    def __init__(self, t_full, p_full):
        self.theory_full_marks = t_full
        self.practical_full_marks = p_full

class MockSubject:
    def __init__(self, name, t_ch, p_ch, has_prac):
        self.name = name
        self.theory_credit_hour = t_ch
        self.practical_credit_hour = p_ch
        self.has_practical = has_prac

class MockMarkEntry:
    def __init__(self, subject, t_obt, p_obt=None):
        self.subject = subject
        self.theory_obtained = t_obt
        self.internal_obtained = p_obt
        self.special_value = None

def test():
    engine = GradingEngine(system='NEB')

    print("--- TEST SCENARIO 1: High Marks (A+) ---")
    ms1 = MockMarkingStructure(75, 25)
    sub1 = MockSubject('Math', 3, 1, True)
    entry1 = MockMarkEntry(sub1, 72, 24)
    # Theory pct = 72/75 = 96% -> A+ (4.0)
    # Internal pct = 24/25 = 96% -> A+ (4.0)
    # WGP = 4.0*3 + 4.0*1 = 16.0
    # GPA = 16.0 / 4 = 4.0 -> A+
    res1 = engine.get_subject_result(entry1, ms1)
    print(f"Theory %: {72/75*100:.1f}%, GP: {res1['theory_grade_point']} ({res1['theory_grade']})")
    print(f"Internal %: {24/25*100:.1f}%, GP: {res1['internal_grade_point']} ({res1['internal_grade']})")
    print(f"Subject GPA: {res1['gpa']}, Final Grade: {res1['grade']}")
    print()

    print("--- TEST SCENARIO 2: Fail Theory (<35%) ---")
    ms2 = MockMarkingStructure(75, 25)
    sub2 = MockSubject('Science', 3, 1, True)
    entry2 = MockMarkEntry(sub2, 25, 20) 
    # Theory pct = 25/75 = 33.3% (<35%) -> Fail -> NG
    res2 = engine.get_subject_result(entry2, ms2)
    print(f"Theory %: {25/75*100:.1f}%, Pass: {res2['is_pass']}")
    print(f"Subject GPA: {res2['gpa']}, Final Grade: {res2['grade']}")
    print()

    print("--- TEST SCENARIO 3: Fail Internal (<40%) ---")
    ms3 = MockMarkingStructure(75, 25)
    sub3 = MockSubject('Computer', 3, 1, True)
    entry3 = MockMarkEntry(sub3, 60, 9) 
    # Theory pct = 60/75 = 80% (Pass)
    # Internal pct = 9/25 = 36% (<40%) -> Fail -> NG
    res3 = engine.get_subject_result(entry3, ms3)
    print(f"Internal %: {9/25*100:.1f}%, Pass: {res3['is_pass']}")
    print(f"Subject GPA: {res3['gpa']}, Final Grade: {res3['grade']}")
    print()

    print("--- TEST SCENARIO 4: Exactly 1.60 GPA (D) ---")
    ms4 = MockMarkingStructure(100, 0)
    sub4 = MockSubject('English', 4, 0, False)
    # Theory exactly 36% -> 36/100 -> D (1.6)
    # 35 to 40% is D (1.6 GP)
    entry4 = MockMarkEntry(sub4, 36) 
    res4 = engine.get_subject_result(entry4, ms4)
    print(f"Theory %: {36/100*100:.1f}%, GP: {res4['theory_grade_point']} ({res4['theory_grade']})")
    print(f"Subject GPA: {res4['gpa']}, Final Grade: {res4['grade']}")
    print()

if __name__ == '__main__':
    test()
