"""
Reports App — Web views
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def reports_index(request):
    school = request.user.school
    active_session = school.get_active_session() if school else None
    from apps.exams.models import Exam
    exams = Exam.objects.filter(school=school, status=Exam.Status.PUBLISHED)
    if active_session:
        exams = exams.filter(session=active_session)
    return render(request, 'reports/index.html', {'exams': exams})


@login_required
def toppers_report(request, exam_id):
    school = request.user.school
    from apps.exams.models import Exam
    from apps.results.models import StudentResult
    exam = get_object_or_404(Exam, pk=exam_id, school=school)
    toppers = StudentResult.objects.filter(
        exam=exam, school=school, is_pass=True
    ).select_related('student', 'student__class_obj').order_by('class_rank')[:20]
    return render(request, 'reports/toppers.html', {'exam': exam, 'toppers': toppers})


@login_required
def merit_list(request, exam_id):
    school = request.user.school
    from apps.exams.models import Exam
    from apps.results.models import StudentResult
    exam = get_object_or_404(Exam, pk=exam_id, school=school)
    results = StudentResult.objects.filter(
        exam=exam, school=school
    ).select_related('student', 'student__class_obj').order_by('class_rank', 'student__roll_number')
    return render(request, 'reports/merit_list.html', {'exam': exam, 'results': results})


@login_required
def pass_fail_report(request, exam_id):
    school = request.user.school
    from apps.exams.models import Exam
    from apps.results.models import StudentResult
    exam = get_object_or_404(Exam, pk=exam_id, school=school)
    total = StudentResult.objects.filter(exam=exam, school=school).count()
    passed = StudentResult.objects.filter(exam=exam, school=school, is_pass=True).count()
    failed_list = StudentResult.objects.filter(
        exam=exam, school=school, is_pass=False
    ).select_related('student', 'student__class_obj')
    return render(request, 'reports/pass_fail.html', {
        'exam': exam, 'total': total, 'passed': passed,
        'failed': total - passed,
        'pass_pct': round(passed / total * 100, 1) if total else 0,
        'failed_list': failed_list,
    })


@login_required
def subject_analysis(request, exam_id, subject_id):
    school = request.user.school
    from apps.exams.models import Exam
    from apps.subjects.models import Subject
    from apps.marks.models import MarkEntry
    exam = get_object_or_404(Exam, pk=exam_id, school=school)
    subject = get_object_or_404(Subject, pk=subject_id, school=school)
    
    if request.user.is_teacher:
        if not subject.assigned_teachers.filter(teacher__user=request.user).exists():
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, 'You can only view reports for subjects you teach.')
            return redirect('teacher_dashboard')

    entries = MarkEntry.objects.filter(
        exam=exam, subject=subject, school=school
    ).select_related('student', 'subject_result')
    return render(request, 'reports/subject_analysis.html', {
        'exam': exam, 'subject': subject, 'entries': entries
    })
