"""
Reports App — Web views
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models.functions import Length
import json


@login_required
def reports_index(request):
    school = request.user.school
    active_session = school.get_active_session() if school else None
    from apps.exams.models import Exam
    exams = Exam.objects.filter(school=school, status=Exam.Status.PUBLISHED)
    if active_session:
        exams = exams.filter(session=active_session)
    exams = exams.order_by('created_at')
    return render(request, 'reports/index.html', {'exams': exams})


@login_required
def toppers_report(request, exam_id):
    school = request.user.school
    from apps.exams.models import Exam
    from apps.results.models import StudentResult
    from apps.classes.models import Class
    exam = get_object_or_404(Exam, pk=exam_id, school=school)
    
    classes = Class.objects.filter(school=school, session=exam.session).order_by('numeric_level', 'name', 'section')
    
    class_id = request.GET.get('class_id')
    toppers = StudentResult.objects.filter(
        exam=exam, school=school, is_pass=True
    ).select_related('student', 'student__class_obj')
    
    if class_id:
        toppers = toppers.filter(student__class_obj_id=class_id)
        
    toppers = toppers.order_by('-overall_gpa', '-percentage')[:20]
    
    # Calculate ranks based purely on GPA (competition rank)
    toppers_list = list(toppers)
    current_rank = 1
    previous_gpa = None
    for idx, t in enumerate(toppers_list):
        if previous_gpa is not None and t.overall_gpa < previous_gpa:
            current_rank = idx + 1
        t.display_rank = current_rank
        previous_gpa = t.overall_gpa

    return render(request, 'reports/toppers.html', {
        'exam': exam, 'toppers': toppers_list,
        'classes': classes,
        'selected_class_id': int(class_id) if class_id and class_id.isdigit() else None,
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
        if not hasattr(request.user, 'teacher_profile') or subject.class_obj.class_teacher != request.user.teacher_profile:
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, "Access denied.")
            return redirect('dashboard')

    entries = MarkEntry.objects.filter(
        exam=exam, subject=subject, school=school
    ).select_related('student', 'subject_result')
    return render(request, 'reports/subject_analysis.html', {
        'exam': exam, 'subject': subject, 'entries': entries
    })


@login_required
def exam_analytics(request, exam_id):
    import json, statistics, math
    from django.db.models import Count, Avg, Max, Min, StdDev
    from apps.exams.models import Exam
    from apps.results.models import StudentResult
    from apps.classes.models import Class
    from apps.marks.models import MarkEntry

    school = request.user.school
    exam = get_object_or_404(Exam, pk=exam_id, school=school)
    
    # Get all classes associated with this exam for the dropdown filter
    all_classes = Class.objects.filter(
        school=school, session=exam.session, exam_classes__exam=exam
    ).distinct().order_by('numeric_level', 'name', 'section')

    # Get class filter if provided
    class_id = request.GET.get('class_id')
    selected_class = None
    if class_id:
        selected_class = get_object_or_404(Class, pk=class_id, school=school)

    results = StudentResult.objects.filter(exam=exam, school=school).select_related('student', 'student__class_obj')
    if selected_class:
        results = results.filter(student__class_obj=selected_class)
        
    total_students = results.count()

    # ── Core Pass/Fail ──────────────────────────────────────────────
    passed = results.filter(is_pass=True).count()
    failed = total_students - passed
    pass_rate = round((passed / total_students * 100), 1) if total_students else 0

    pass_fail_stats = {
        'passed': passed, 'failed': failed,
        'pass_rate': pass_rate, 'fail_rate': round(100 - pass_rate, 1)
    }

    # ── GPA stats ────────────────────────────────────────────────────
    gpa_values = [float(r.overall_gpa) for r in results if r.overall_gpa is not None]
    avg_gpa = round(statistics.mean(gpa_values), 2) if gpa_values else 0
    median_gpa = round(statistics.median(gpa_values), 2) if gpa_values else 0
    std_gpa = round(statistics.stdev(gpa_values), 3) if len(gpa_values) > 1 else 0
    min_gpa = round(min(gpa_values), 2) if gpa_values else 0
    max_gpa = round(max(gpa_values), 2) if gpa_values else 0

    # Percentiles
    def percentile(data, pct):
        if not data: return 0
        s = sorted(data)
        k = (len(s) - 1) * pct / 100
        lo, hi = int(k), math.ceil(k)
        return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)

    p25 = percentile(gpa_values, 25)
    p75 = percentile(gpa_values, 75)
    p90 = percentile(gpa_values, 90)

    # ── Grade Distribution ───────────────────────────────────────────
    grade_order = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D', 'NG']
    grade_counts = results.values('final_grade').annotate(count=Count('id'))
    grade_dist = {g: 0 for g in grade_order}
    for item in grade_counts:
        g = item['final_grade']
        if g in grade_dist:
            grade_dist[g] = item['count']

    # ── GPA Distribution buckets ─────────────────────────────────────
    gpa_dist = {
        '3.6–4.0': 0, '3.2–3.59': 0, '2.8–3.19': 0,
        '2.4–2.79': 0, '2.0–2.39': 0, '1.6–1.99': 0, '<1.6': 0
    }
    perf_categories = {'Excellent': 0, 'Good': 0, 'Average': 0, 'Needs Improvement': 0}
    for g in gpa_values:
        if g >= 3.6:   gpa_dist['3.6–4.0'] += 1;   perf_categories['Excellent'] += 1
        elif g >= 3.2: gpa_dist['3.2–3.59'] += 1;  perf_categories['Good'] += 1
        elif g >= 2.8: gpa_dist['2.8–3.19'] += 1;  perf_categories['Good'] += 1
        elif g >= 2.4: gpa_dist['2.4–2.79'] += 1;  perf_categories['Average'] += 1
        elif g >= 2.0: gpa_dist['2.0–2.39'] += 1;  perf_categories['Average'] += 1
        elif g >= 1.6: gpa_dist['1.6–1.99'] += 1;  perf_categories['Needs Improvement'] += 1
        else:          gpa_dist['<1.6'] += 1;        perf_categories['Needs Improvement'] += 1

    # ── Gender breakdown ─────────────────────────────────────────────
    gender_stats = {}
    for gender_code, gender_label in [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]:
        g_results = results.filter(student__gender=gender_code)
        g_total = g_results.count()
        if g_total > 0:
            g_passed = g_results.filter(is_pass=True).count()
            g_gpas = [float(r.overall_gpa) for r in g_results if r.overall_gpa is not None]
            gender_stats[gender_label] = {
                'total': g_total,
                'passed': g_passed,
                'pass_rate': round(g_passed / g_total * 100, 1),
                'avg_gpa': round(statistics.mean(g_gpas), 2) if g_gpas else 0,
            }
    # ── Failure Severity Index & Subject Failure Heatmap ─────────────
    failure_severity = {'one': 0, 'two': 0, 'three_plus': 0}
    subject_failure_counts = {}
    
    for r in results:
        if r.failed_subjects:
            num_failed = len(r.failed_subjects)
            if num_failed == 1:
                failure_severity['one'] += 1
            elif num_failed == 2:
                failure_severity['two'] += 1
            elif num_failed >= 3:
                failure_severity['three_plus'] += 1
                
            for subj in r.failed_subjects:
                subject_failure_counts[subj] = subject_failure_counts.get(subj, 0) + 1
                
    subject_failure_heatmap = []
    for subj, count in sorted(subject_failure_counts.items(), key=lambda x: x[1], reverse=True):
        pct = round((count / total_students * 100)) if total_students else 0
        subject_failure_heatmap.append({
            'subject': subj,
            'count': count,
            'fail_pct': pct
        })

    # ── Class Analytics ───────────────────────────────────────────────
    class_stats = []
    classes = Class.objects.filter(
        school=school, session=exam.session, exam_classes__exam=exam
    ).distinct().order_by('-numeric_level', 'name', 'section')

    for cls in classes:
        cls_results = results.filter(student__class_obj=cls)
        cls_total = cls_results.count()
        if cls_total == 0:
            continue
        # Skip classes that do not have any computed results/GPAs
        if not cls_results.filter(overall_gpa__isnull=False).exists():
            continue
        cls_passed = cls_results.filter(is_pass=True).count()
        cls_pass_rate = round((cls_passed / cls_total) * 100, 1)
        agg = cls_results.aggregate(
            avg_gpa=Avg('overall_gpa'),
            avg_marks=Avg('total_marks_obtained'),
            max_gpa=Max('overall_gpa'),
            min_gpa=Min('overall_gpa'),
        )
        class_stats.append({
            'name': cls.full_name,
            'avg_gpa': round(float(agg['avg_gpa']), 2) if agg['avg_gpa'] else 0,
            'pass_rate': cls_pass_rate,
            'avg_marks': round(float(agg['avg_marks']), 2) if agg['avg_marks'] else 0,
            'max_gpa': round(float(agg['max_gpa']), 2) if agg['max_gpa'] else 0,
            'min_gpa': round(float(agg['min_gpa']), 2) if agg['min_gpa'] else 0,
            'total_students': cls_total,
            'passed': cls_passed,
        })

    # ── Subject-wise average marks ────────────────────────────────────
    from django.db.models import F, ExpressionWrapper, FloatField
    mark_entries = MarkEntry.objects.filter(exam=exam, school=school, special_value__isnull=True)
    if selected_class:
        mark_entries = mark_entries.filter(student__class_obj=selected_class)

    subject_avgs = (
        mark_entries
        .values('subject__name', 'subject__code')
        .annotate(
            avg_theory=Avg('theory_obtained'),
            avg_internal=Avg('internal_obtained'),
            count=Count('id'),
        )
        .order_by('-avg_theory')[:12]
    )
    subj_labels = [f"{s['subject__code']}" for s in subject_avgs]
    subj_avg_data = [round((float(s['avg_theory'] or 0) + float(s['avg_internal'] or 0)), 1) for s in subject_avgs]
    subj_names = [s['subject__name'] for s in subject_avgs]

    # ── Detail Analysis (Radar Chart Data) ───────────────────────────
    # For individual student radar charts: mapping student ID -> data
    student_radar_data = {}
    students_for_radar = []
    
    # mark_entries is already filtered by exam, school, and selected_class (if any)
    for me in mark_entries.select_related('student', 'subject', 'student__class_obj').order_by('student__name'):
        sid = str(me.student_id)
        if sid not in student_radar_data:
            cls_name = me.student.class_obj.full_name if me.student.class_obj else 'Unknown Class'
            cls_id = str(me.student.class_obj.id) if me.student.class_obj else '0'
            student_radar_data[sid] = {
                'id': sid,
                'name': me.student.name,
                'roll': me.student.roll_number or '-',
                'class_name': cls_name,
                'class_id': cls_id,
                'labels': [],
                'data': []
            }
            students_for_radar.append({
                'id': sid, 
                'name': me.student.name, 
                'roll': me.student.roll_number or '-',
                'class_name': cls_name,
                'class_id': cls_id
            })
        
        # Calculate percentage for the subject
        th_obt = float(me.theory_obtained) if me.theory_obtained else 0.0
        int_obt = float(me.internal_obtained) if me.internal_obtained else 0.0
        tot_obt = th_obt + int_obt
        
        th_full = float(me.subject.theory_full_marks) if me.subject.theory_full_marks else 0.0
        int_full = float(me.subject.practical_full_marks) if me.subject.practical_full_marks else 0.0
        tot_full = th_full + int_full
        
        pct = round((tot_obt / tot_full * 100), 1) if tot_full > 0 else 0
        
        student_radar_data[sid]['labels'].append(me.subject.name)
        student_radar_data[sid]['data'].append(pct)
    students_for_radar.sort(key=lambda x: (int(x['roll']) if str(x['roll']).isdigit() else 99999, x['name']))

    # ── Bee-Swarm data: each student's GPA with class label ──────────
    swarm_data = []
    for r in results:
        if r.overall_gpa is not None and r.student.class_obj:
            swarm_data.append({
                'x': round(float(r.overall_gpa), 2),
                'name': r.student.name,
                'cls': r.student.class_obj.full_name,
                'grade': r.final_grade,
                'pass': r.is_pass,
            })

    # ── Percentage distribution (histogram bins) ─────────────────────
    pct_bins = [f"{i}–{i+10}%" for i in range(0, 100, 10)]
    pct_counts = [0] * 10
    for r in results:
        if r.percentage is not None:
            idx = min(int(float(r.percentage) // 10), 9)
            pct_counts[idx] += 1

    # ── Attendance vs Performance Correlation ────────────────────────
    attendance_correlation_data = []
    
    mark_entries = MarkEntry.objects.filter(
        exam=exam, 
        school=school, 
        total_days__gt=0, 
        present_days__isnull=False
    ).select_related('student')
    attendance_map = {}
    for me in mark_entries:
        sid = me.student_id
        if sid not in attendance_map:
            attendance_map[sid] = {'present': 0, 'total': 0}
        attendance_map[sid]['present'] += me.present_days
        attendance_map[sid]['total'] += me.total_days
        
    attendance_excellence_count = 0
    absence_risk_count = 0
    
    for r in results:
        sid = r.student_id
        if sid in attendance_map and r.overall_gpa is not None:
            att = attendance_map[sid]
            if att['total'] > 0:
                pct = round((att['present'] / att['total']) * 100, 1)
                
                if pct >= 90:
                    attendance_excellence_count += 1
                elif pct < 75:
                    absence_risk_count += 1
                    
                attendance_correlation_data.append({
                    'x': pct,
                    'y': round(float(r.overall_gpa), 2),
                    'name': r.student.name,
                    'pass': r.is_pass
                })

    # ── Attendance Impact Score ───────────────────────────────────────
    # "X% of failed students had <75% attendance"
    failed_students_ids = set(r.student_id for r in results if not r.is_pass)
    low_att_failed = 0
    for r in results:
        sid = r.student_id
        if sid in failed_students_ids and sid in attendance_map:
            att = attendance_map[sid]
            if att['total'] > 0:
                pct = (att['present'] / att['total']) * 100
                if pct < 75:
                    low_att_failed += 1
    attendance_impact_pct = round((low_att_failed / len(failed_students_ids) * 100)) if failed_students_ids else 0
    attendance_impact = {
        'pct': attendance_impact_pct,
        'count': low_att_failed,
        'failed_total': len(failed_students_ids),
    }

    # ── Grade Velocity (Borderline Zone) ─────────────────────────────
    # Students with GPA 2.0–2.6 who failed — intervention candidates
    borderline_students = []
    for r in results:
        if r.overall_gpa is not None:
            gpa = float(r.overall_gpa)
            if 2.0 <= gpa <= 2.6:
                borderline_students.append({
                    'name': r.student.name,
                    'gpa': round(gpa, 2),
                    'grade': r.final_grade or '—',
                    'class': r.student.class_obj.full_name if r.student.class_obj else '—',
                    'is_pass': r.is_pass,
                })
    borderline_students.sort(key=lambda x: x['gpa'], reverse=True)

    # ── Top Improvers & Biggest Decliners ────────────────────────────
    # Find most recent prior exam in the same session (occurring before this one)
    prior_exam = None
    if exam.start_date:
        prior_exam = (
            Exam.objects.filter(
                school=school,
                session=exam.session,
                start_date__lt=exam.start_date
            )
            .exclude(pk=exam.pk)
            .order_by('-start_date', '-created_at')
            .first()
        )
        # Fallback: any prior exam for this school occurring before this one
        if not prior_exam:
            prior_exam = (
                Exam.objects.filter(
                    school=school,
                    start_date__lt=exam.start_date
                )
                .exclude(pk=exam.pk)
                .order_by('-start_date', '-created_at')
                .first()
            )

    top_improvers = []
    biggest_decliners = []
    if prior_exam:
        # Fetch ALL results from prior exam — including failed students (gpa may be None)
        prior_results_qs = StudentResult.objects.filter(
            exam=prior_exam, school=school
        ).select_related('student', 'student__class_obj')
        
        # Use percentage as the comparable metric since failed students have NULL gpa.
        # Fall back to 0.0 if both gpa and percentage are None.
        def score_of(result):
            if result.overall_gpa is not None:
                return float(result.overall_gpa)
            if result.percentage is not None:
                # Normalise percentage to 0–4 GPA scale for delta comparison
                return round(float(result.percentage) / 25, 2)
            return 0.0

        prior_map = {}
        for pr in prior_results_qs:
            prior_map[pr.student_id] = {
                'score': score_of(pr),
                'gpa_display': str(pr.overall_gpa) if pr.overall_gpa is not None else 'NG',
            }

        # Current results — also include failed students
        all_current = StudentResult.objects.filter(
            exam=exam, school=school
        ).select_related('student', 'student__class_obj')

        deltas = []
        for r in all_current:
            if r.student_id in prior_map:
                prev_score = prior_map[r.student_id]['score']
                curr_score = score_of(r)
                delta = round(curr_score - prev_score, 2)
                curr_gpa_display = str(r.overall_gpa) if r.overall_gpa is not None else 'NG'
                prev_gpa_display = prior_map[r.student_id]['gpa_display']
                # Only include if there's a meaningful change or the student changed pass/fail status
                deltas.append({
                    'name': r.student.name,
                    'class': r.student.class_obj.full_name if r.student.class_obj else '—',
                    'prev_gpa': prev_gpa_display,
                    'curr_gpa': curr_gpa_display,
                    'delta': delta,
                    'is_pass': r.is_pass,
                })
        deltas.sort(key=lambda x: x['delta'], reverse=True)
        top_improvers = [d for d in deltas if d['delta'] > 0][:10]
        biggest_decliners = [d for d in sorted(deltas, key=lambda x: x['delta']) if d['delta'] < 0][:10]

    # ── Radar: average subject GPA per performance group ─────────────
    top_subjects = subj_labels[:6]  # use top 6 for radar


    return render(request, 'reports/analytics.html', {
        'exam': exam,
        'total_students': total_students,
        'pass_fail_stats': pass_fail_stats,
        # KPI stats
        'avg_gpa': avg_gpa,
        'median_gpa': median_gpa,
        'std_gpa': std_gpa,
        'min_gpa': min_gpa,
        'max_gpa': max_gpa,
        'p25': p25, 'p75': p75, 'p90': p90,
        # Grade / GPA dist
        'grade_dist_labels': json.dumps(grade_order),
        'grade_dist_data': json.dumps([grade_dist[g] for g in grade_order]),
        'gpa_dist_labels': json.dumps(list(gpa_dist.keys())),
        'gpa_dist_data': json.dumps(list(gpa_dist.values())),
        # Performance
        'perf_categories': perf_categories,
        # Failure Analytics
        'failure_severity': failure_severity,
        'subject_failure_heatmap': subject_failure_heatmap,
        # Attendance Analytics
        'attendance_excellence_count': attendance_excellence_count,
        'absence_risk_count': absence_risk_count,
        'attendance_impact': attendance_impact,
        # Grade Velocity
        'borderline_students': borderline_students,
        'borderline_count': len(borderline_students),
        # Improvers / Decliners
        'prior_exam': prior_exam,
        'top_improvers': top_improvers,
        'biggest_decliners': biggest_decliners,
        # Gender
        'gender_stats': gender_stats,
        'gender_labels': json.dumps(list(gender_stats.keys())),
        'gender_pass_rates': json.dumps([v['pass_rate'] for v in gender_stats.values()]),
        'gender_avg_gpas': json.dumps([v['avg_gpa'] for v in gender_stats.values()]),
        # Class analytics
        'class_stats': class_stats,
        'class_labels_json': json.dumps([c['name'] for c in class_stats]),
        'class_gpa_json': json.dumps([c['avg_gpa'] for c in class_stats]),
        'class_pass_json': json.dumps([c['pass_rate'] for c in class_stats]),
        'class_min_gpa_json': json.dumps([c['min_gpa'] for c in class_stats]),
        'class_max_gpa_json': json.dumps([c['max_gpa'] for c in class_stats]),
        # Subject analysis
        'subj_labels': json.dumps(subj_labels),
        'subj_avg_data': json.dumps(subj_avg_data),
        'subj_names': json.dumps(subj_names),
        # Bee-swarm
        'swarm_data': json.dumps(swarm_data),
        # Percentage histogram
        'pct_bins': json.dumps(pct_bins),
        'pct_counts': json.dumps(pct_counts),
        'attendance_correlation_json': json.dumps(attendance_correlation_data),
        # Detail Analysis Radar
        'student_radar_data_json': json.dumps(student_radar_data),
        'students_for_radar': students_for_radar,
        'students_for_radar_json': json.dumps(students_for_radar),
        # Class Filter context
        'all_classes': all_classes,
        'selected_class': selected_class,
        'available_exams': Exam.objects.filter(school=school, session=exam.session, status='PUBLISHED').exclude(pk=exam.pk),
    })


@login_required
def export_toppers_pdf(request, exam_id):
    school = request.user.school
    from apps.exams.models import Exam
    from apps.results.models import StudentResult
    from apps.classes.models import Class
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    exam = get_object_or_404(Exam, pk=exam_id, school=school)
    classes = Class.objects.filter(school=school, session=exam.session).order_by('numeric_level', 'name', 'section')

    # Gather top 3 students for all classes (handling ties)
    data = []
    for cls in classes:
        # Sort by GPA descending, then percentage descending as a secondary tie-breaker
        results = StudentResult.objects.filter(
            exam=exam, school=school, student__class_obj=cls, is_pass=True, overall_gpa__isnull=False
        ).select_related('student').order_by('-overall_gpa', '-percentage')

        # Find the top 3 unique GPA values
        unique_gpas = []
        for r in results:
            g = r.overall_gpa
            if g not in unique_gpas:
                unique_gpas.append(g)
                if len(unique_gpas) == 3:
                    break

        # Filter students who hold any of these top 3 GPA values
        toppers = [r for r in results if r.overall_gpa in unique_gpas]

        if toppers:
            toppers_data = []
            current_rank = 1
            previous_gpa = None
            for idx, t in enumerate(toppers):
                if previous_gpa is not None and t.overall_gpa < previous_gpa:
                    current_rank = idx + 1
                previous_gpa = t.overall_gpa
                toppers_data.append({
                    'rank': current_rank,
                    'student_name': t.student.name,
                    'gpa': t.overall_gpa,
                    'grade': t.final_grade or '—'
                })

            data.append({
                'class': cls,
                'toppers': toppers_data
            })

    # Create PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="toppers_{exam.name.replace(" ", "_")}.pdf"'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#475569'),
        alignment=TA_CENTER
    )
    class_title_style = ParagraphStyle(
        'ClassTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#2563EB'),
        spaceBefore=12,
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white
    )

    story = []

    # Header block
    story.append(Paragraph(school.name, title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Top Performers of All Classes — {exam.name}", subtitle_style))
    story.append(Paragraph(f"Academic Session: {exam.session.name}", subtitle_style))
    story.append(Spacer(1, 15))

    if not data:
        story.append(Paragraph("No topper data available for this exam. Make sure results are processed.", subtitle_style))
    else:
        for item in data:
            cls = item['class']
            toppers = item['toppers']

            story.append(Paragraph(cls.full_name, class_title_style))

            table_data = [[
                Paragraph("Rank", header_style),
                Paragraph("Student Name", header_style),
                Paragraph("GPA", header_style),
                Paragraph("Grade", header_style),
            ]]

            for t in toppers:
                table_data.append([
                    Paragraph(str(t['rank']), cell_style),
                    Paragraph(t['student_name'], cell_style),
                    Paragraph(f"{t['gpa']:.2f}" if t['gpa'] else '—', cell_style),
                    Paragraph(t['grade'], cell_style),
                ])

            t_table = Table(table_data, colWidths=[50, 325, 70, 70])
            t_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(t_table)
            story.append(Spacer(1, 10))

    doc.build(story)
    pdf_content = buffer.getvalue()
    buffer.close()

    response.write(pdf_content)
    return response




@login_required
def compare_analytics(request):
    import json
    from django.db.models import Avg, Count, Max, Min, Q
    from apps.exams.models import Exam
    from apps.classes.models import Class
    from apps.results.models import StudentResult, SubjectResult
    from apps.marks.models import MarkEntry

    school = request.user.school
    
    exam_ids_str = request.GET.get('exams', '')
    exam_ids = [int(eid) for eid in exam_ids_str.split(',') if eid.isdigit()]
    class_id = request.GET.get('class_id')
    
    selected_class = None
    if class_id and class_id.isdigit():
        selected_class = get_object_or_404(Class, pk=class_id, school=school)
        
    exams = list(Exam.objects.filter(pk__in=exam_ids, school=school).order_by('start_date'))
    if not exams:
        return render(request, 'reports/compare_analytics.html', {'exams': exams})

    # Base querysets
    res_qs = StudentResult.objects.filter(exam__in=exams, school=school)
    sub_qs = SubjectResult.objects.filter(mark_entry__exam__in=exams, mark_entry__student__school=school)
    
    if selected_class:
        res_qs = res_qs.filter(student__class_obj=selected_class)
        sub_qs = sub_qs.filter(mark_entry__student__class_obj=selected_class)

    # --- 1. KPIs (Compare first exam vs last exam) ---
    def get_exam_stats(exam_obj):
        qs = res_qs.filter(exam=exam_obj)
        total = qs.count()
        if total == 0:
            return {'pass_rate': 0, 'avg_gpa': 0, 'failed': 0, 'top': 0, 'high': 0, 'low': 0}
        passed = qs.filter(is_pass=True).count()
        failed = total - passed
        avg = qs.aggregate(Avg('overall_gpa'))['overall_gpa__avg'] or 0
        top = qs.filter(final_grade__in=['A+', 'A']).count()
        high = qs.aggregate(Max('overall_gpa'))['overall_gpa__max'] or 0
        low = qs.aggregate(Min('overall_gpa'))['overall_gpa__min'] or 0
        return {
            'pass_rate': (passed / total) * 100,
            'avg_gpa': float(avg),
            'failed': failed,
            'top': top,
            'high': float(high),
            'low': float(low)
        }

    first_stats = get_exam_stats(exams[0])
    last_stats = get_exam_stats(exams[-1]) if len(exams) > 1 else first_stats
    
    def calc_trend(v1, v2):
        if v2 > v1: return 'up'
        if v2 < v1: return 'down'
        return 'flat'

    kpis = {
        'pass_rate': {'value': round(last_stats['pass_rate'], 1), 'trend': calc_trend(first_stats['pass_rate'], last_stats['pass_rate'])},
        'avg_gpa': {'value': round(last_stats['avg_gpa'], 2), 'trend': calc_trend(first_stats['avg_gpa'], last_stats['avg_gpa'])},
        'failed_students': {'value': last_stats['failed'], 'trend': calc_trend(first_stats['failed'], last_stats['failed'])},
        'top_grade_count': {'value': last_stats['top'], 'trend': calc_trend(first_stats['top'], last_stats['top'])},
        'highest_gpa': {'value': round(last_stats['high'], 2), 'trend': calc_trend(first_stats['high'], last_stats['high'])},
        'lowest_gpa': {'value': round(last_stats['low'], 2), 'trend': calc_trend(first_stats['low'], last_stats['low'])},
    }

    # Helper maps
    exam_names = [e.name for e in exams]

    # --- 2. Dumbbell Chart (Pass / Fail Ratio) ---
    dumbbell_data = []
    for e in exams:
        qs = res_qs.filter(exam=e)
        t = qs.count()
        p = qs.filter(is_pass=True).count()
        dumbbell_data.append({
            'exam': e.name,
            'pass_pct': round((p/t*100) if t else 0, 1),
            'fail_pct': round(((t-p)/t*100) if t else 0, 1)
        })

    # --- 3. Grouped Bar Chart (Grade Distribution) ---
    grades = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'E']
    grade_dist_data = {
        'labels': grades,
        'datasets': []
    }
    colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16']
    for idx, e in enumerate(exams):
        counts = []
        for g in grades:
            counts.append(res_qs.filter(exam=e, final_grade=g).count())
        grade_dist_data['datasets'].append({
            'label': e.name,
            'data': counts,
            'backgroundColor': colors[idx % len(colors)]
        })

    # --- 4. Horizontal Bar Chart (Subject Average Comparison) ---
    # Get top subjects by participation
    subs = list(sub_qs.values_list('mark_entry__subject__name', flat=True).distinct())
    subject_avg_data = {
        'labels': subs,
        'datasets': []
    }
    for idx, e in enumerate(exams):
        d = []
        for s in subs:
            a = sub_qs.filter(mark_entry__exam=e, mark_entry__subject__name=s).aggregate(Avg('gpa'))['gpa__avg'] or 0
            d.append(float(round(a, 2)))
        subject_avg_data['datasets'].append({
            'label': e.name,
            'data': d,
            'backgroundColor': colors[idx % len(colors)]
        })

    # --- 5 & 6. Clustered Column Chart (Average GPA / Pass Rate by Class) ---
    if not selected_class:
        classes = list(Class.objects.filter(school=school).order_by('name'))
        class_names = [c.name for c in classes]
    else:
        classes = [selected_class]
        class_names = [selected_class.name]
        
    class_gpa_datasets = []
    class_pass_datasets = []
    heatmap_matrix = [] # for Heatmap later
    
    for idx, e in enumerate(exams):
        gpas = []
        passes = []
        heat_row = []
        for c in classes:
            c_qs = res_qs.filter(exam=e, student__class_obj=c)
            t = c_qs.count()
            p = c_qs.filter(is_pass=True).count()
            a = c_qs.aggregate(Avg('overall_gpa'))['overall_gpa__avg'] or 0
            
            gpas.append(float(round(a, 2)))
            passes.append(round((p/t*100) if t else 0, 1))
            heat_row.append(float(round(a, 2)))
            
        class_gpa_datasets.append({'label': e.name, 'data': gpas, 'backgroundColor': colors[idx % len(colors)]})
        class_pass_datasets.append({'label': e.name, 'data': passes, 'backgroundColor': colors[idx % len(colors)]})
        heatmap_matrix.append({'exam': e.name, 'data': heat_row})
        
    class_gpa_data = {'labels': class_names, 'datasets': class_gpa_datasets}
    class_pass_data = {'labels': class_names, 'datasets': class_pass_datasets}

    # --- 7. Diverging Bar Chart (Subject Improvement N vs 1) ---
    subject_improvement = {'labels': [], 'data': []}
    if len(exams) >= 2:
        e_first = exams[0]
        e_last = exams[-1]
        for s in subs:
            avg_f = float(sub_qs.filter(mark_entry__exam=e_first, mark_entry__subject__name=s).aggregate(Avg('gpa'))['gpa__avg'] or 0)
            avg_l = float(sub_qs.filter(mark_entry__exam=e_last, mark_entry__subject__name=s).aggregate(Avg('gpa'))['gpa__avg'] or 0)
            diff = float(round(avg_l - avg_f, 2))
            subject_improvement['labels'].append(s)
            subject_improvement['data'].append(diff)

    # --- 8. Radar Chart (Overall Subject Performance) ---
    # Re-use subject_avg_data logic but format for Radar (borderColor instead of backgroundColor)
    radar_datasets = []
    for idx, e in enumerate(exams):
        d = subject_avg_data['datasets'][idx]['data']
        col = colors[idx % len(colors)]
        radar_datasets.append({
            'label': e.name,
            'data': d,
            'borderColor': col,
            'backgroundColor': f"{col}33",
            'borderWidth': 2,
            'pointBackgroundColor': col
        })
    radar_data = {'labels': subs, 'datasets': radar_datasets}

    # --- 9. Heatmap (Class Performance Matrix) ---
    # Data prepared in heatmap_matrix + class_names

    # --- 10. Line Chart (Overall GPA Trend) ---
    gpa_trend = []
    for e in exams:
        a = res_qs.filter(exam=e).aggregate(Avg('overall_gpa'))['overall_gpa__avg'] or 0
        gpa_trend.append(float(round(a, 2)))

    context = {
        'exams': exams,
        'selected_class': selected_class,
        'exam_names_json': json.dumps(exam_names),
        'kpis': kpis,
        'dumbbell_data_json': json.dumps(dumbbell_data),
        'grade_dist_data_json': json.dumps(grade_dist_data),
        'subject_avg_data_json': json.dumps(subject_avg_data),
        'class_gpa_data_json': json.dumps(class_gpa_data),
        'class_pass_data_json': json.dumps(class_pass_data),
        'subject_improvement_json': json.dumps(subject_improvement),
        'radar_data_json': json.dumps(radar_data),
        'class_names_json': json.dumps(class_names),
        'heatmap_matrix_json': json.dumps(heatmap_matrix),
        'gpa_trend_json': json.dumps(gpa_trend),
    }
    return render(request, 'reports/compare_analytics.html', context)
