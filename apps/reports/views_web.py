"""
Reports App — Web views
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models.functions import Length


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
    from apps.classes.models import Class
    exam = get_object_or_404(Exam, pk=exam_id, school=school)
    
    classes = Class.objects.filter(school=school, session=exam.session).order_by('numeric_level', 'name', 'section')
    
    class_id = request.GET.get('class_id')
    toppers = StudentResult.objects.filter(
        exam=exam, school=school, is_pass=True
    ).select_related('student', 'student__class_obj')
    
    if class_id:
        toppers = toppers.filter(student__class_obj_id=class_id)
        
    toppers = toppers.order_by('class_rank')[:20]
    return render(request, 'reports/toppers.html', {
        'exam': exam, 'toppers': toppers,
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
    results = StudentResult.objects.filter(exam=exam, school=school).select_related('student', 'student__class_obj')
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
    subject_avgs = (
        MarkEntry.objects.filter(exam=exam, school=school, special_value__isnull=True)
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
        
    for r in results:
        sid = r.student_id
        if sid in attendance_map and r.overall_gpa is not None:
            att = attendance_map[sid]
            if att['total'] > 0:
                pct = round((att['present'] / att['total']) * 100, 1)
                attendance_correlation_data.append({
                    'x': pct,
                    'y': round(float(r.overall_gpa), 2),
                    'name': r.student.name,
                    'pass': r.is_pass
                })

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


