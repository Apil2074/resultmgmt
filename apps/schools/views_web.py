"""
Schools App — Web views (Dashboard, School Profile, Academic Sessions)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout
from django.db.models import Count, Q
from .models import School, AcademicSession


from apps.accounts.models import User
from apps.audit.models import AuditLog


@login_required
def dashboard(request):
    """Main dashboard with KPIs and recent activity."""
    user = request.user
    school = user.school

    if not school and not user.is_super_admin:
        logout(request)
        messages.error(request, 'No school assigned to your account.')
        return redirect('login')

    if user.is_teacher:
        return redirect('teacher_dashboard')

    # Dashboard stats
    from apps.classes.models import Class
    from apps.students.models import Student
    from apps.subjects.models import Subject
    from apps.exams.models import Exam
    from apps.results.models import StudentResult
    from apps.audit.models import AuditLog

    ctx = {}

    if school:
        active_session = school.get_active_session()
        ctx['active_session'] = active_session

        classes_qs = Class.objects.filter(school=school)
        students_qs = Student.objects.filter(school=school, is_active=True)
        subjects_qs = Subject.objects.filter(school=school)
        exams_qs = Exam.objects.filter(school=school)
        results_qs = StudentResult.objects.filter(school=school)

        if active_session:
            classes_qs = classes_qs.filter(session=active_session)
            students_qs = students_qs.filter(class_obj__session=active_session)
            subjects_qs = subjects_qs.filter(class_obj__session=active_session)
            exams_qs = exams_qs.filter(session=active_session)
            results_qs = results_qs.filter(exam__session=active_session)

        ctx['total_classes'] = classes_qs.count()
        ctx['total_students'] = students_qs.count()
        ctx['total_subjects'] = subjects_qs.count()
        ctx['total_exams'] = exams_qs.count()
        ctx['published_exams'] = exams_qs.filter(
            status=Exam.Status.PUBLISHED
        ).count()

        # Pass percentage across published exams
        total_results = results_qs.count()
        passed_results = results_qs.filter(is_pass=True).count()
        ctx['pass_percentage'] = (
            round((passed_results / total_results) * 100, 1) if total_results else 0
        )

        # Recent activity
        ctx['recent_activities'] = AuditLog.objects.filter(
            school=school
        ).select_related('user').order_by('-timestamp')[:10]

        # Recent exams
        ctx['recent_exams'] = exams_qs.order_by('-created_at')[:5]

        # GPA distribution data for chart
        from apps.results.models import StudentResult
        gpa_data = {}
        for result in results_qs:
            grade = result.final_grade or 'NG'
            gpa_data[grade] = gpa_data.get(grade, 0) + 1
        ctx['gpa_data'] = gpa_data

    elif user.is_super_admin:
        ctx['total_schools'] = School.objects.count()
        ctx['total_students'] = 0
        ctx['all_schools'] = School.objects.annotate(
            student_count=Count('students')
        ).order_by('name')

    return render(request, 'dashboard/index.html', ctx)


@login_required
def school_profile(request):
    """View/edit the current school's profile."""
    school = request.user.school
    if not school:
        messages.error(request, 'No school assigned.')
        return redirect('dashboard')

    if request.method == 'POST':
        # Restrict name and establishment year changes to Super Admins
        if request.user.is_super_admin:
            school.name = request.POST.get('name', school.name)
            school.establishment_year = request.POST.get('establishment_year') or None
            school.subscription_start_date = request.POST.get('subscription_start_date') or None
            school.subscription_end_date = request.POST.get('subscription_end_date') or None

        school.address = request.POST.get('address', school.address)
        school.phone = request.POST.get('phone', school.phone)
        school.email = request.POST.get('email', school.email)
        school.website = request.POST.get('website', school.website)
        school.principal_name = request.POST.get('principal_name', school.principal_name)
        school.exam_head_name = request.POST.get('exam_head_name', school.exam_head_name)
        school.grading_system = request.POST.get('grading_system', school.grading_system)

        if 'logo' in request.FILES:
            school.logo = request.FILES['logo']

        school.save()
        messages.success(request, 'School profile updated successfully.')
        return redirect('school_profile')

    return render(request, 'schools/profile.html', {
        'school': school,
        'grading_system_choices': School.GradingSystem.choices
    })


@login_required
def session_list(request):
    """Manage academic sessions."""
    school = request.user.school
    sessions = AcademicSession.objects.filter(school=school).order_by('-name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            if name:
                session, created = AcademicSession.objects.get_or_create(
                    school=school, name=name
                )
                if created:
                    messages.success(request, f'Session "{name}" created.')
                else:
                    messages.warning(request, f'Session "{name}" already exists.')
            else:
                messages.error(request, 'Session name is required.')

        elif action == 'activate':
            session_id = request.POST.get('session_id')
            session = get_object_or_404(AcademicSession, pk=session_id, school=school)
            session.is_active = True
            session.save()
            messages.success(request, f'Session "{session.name}" is now active.')

        elif action == 'delete':
            session_id = request.POST.get('session_id')
            session = get_object_or_404(AcademicSession, pk=session_id, school=school)
            if not session.is_active:
                session.delete()
                messages.success(request, 'Session deleted.')
            else:
                messages.error(request, 'Cannot delete the active session.')

        return redirect('session_list')

    return render(request, 'schools/sessions.html', {
        'sessions': sessions,
        'school': school,
    })


@login_required
def super_schools(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Only Super Admins can manage schools.")
        return redirect('dashboard')
    
    schools = School.objects.annotate(
        student_count=Count('students', distinct=True),
        admin_count=Count('users', filter=Q(users__role='SCHOOL_ADMIN'), distinct=True)
    ).order_by('name')
    
    return render(request, 'schools/super_schools_list.html', {
        'schools': schools
    })


@login_required
def create_school_and_admin(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Only Super Admins can create schools.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        # School fields
        school_name = request.POST.get('school_name', '').strip()
        est_year = request.POST.get('establishment_year', '').strip()
        address = request.POST.get('address', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        principal = request.POST.get('principal_name', '').strip()
        grading = request.POST.get('grading_system', 'NEB')
        sub_start = request.POST.get('subscription_start_date', '').strip() or None
        sub_end = request.POST.get('subscription_end_date', '').strip() or None
        
        # Admin fields
        username = request.POST.get('username', '').strip()
        user_email = request.POST.get('user_email', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        
        if not (school_name and address and phone and email and principal and username and password and user_email):
            messages.error(request, "Please fill in all required fields.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' is already taken.")
        else:
            try:
                # 1. Create School
                school = School.objects.create(
                    name=school_name,
                    establishment_year=int(est_year) if est_year else None,
                    address=address,
                    phone=phone,
                    email=email,
                    principal_name=principal,
                    grading_system=grading,
                    subscription_start_date=sub_start,
                    subscription_end_date=sub_end
                )
                
                # 2. Create User
                user = User.objects.create_user(
                    username=username,
                    email=user_email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=User.Role.SCHOOL_ADMIN,
                    school=school
                )
                
                # 3. Log Audit
                AuditLog.objects.create(
                    school=school,
                    user=request.user,
                    action=AuditLog.Action.CREATE,
                    model_name='School',
                    object_id=str(school.pk),
                    object_repr=f"School: {school.name} & Admin: {user.username}"
                )
                
                messages.success(request, f"Successfully created school '{school.name}' and admin user '{user.username}'.")
                return redirect('super_schools')
            except Exception as e:
                messages.error(request, f"Error creating school and admin: {str(e)}")
                
    return render(request, 'schools/create_school_and_admin.html', {
        'grading_system_choices': School.GradingSystem.choices
    })


@login_required
def edit_school(request, school_id):
    """Super Admin view to edit an existing school tenant's details."""
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Only Super Admins can edit school details.")
        return redirect('dashboard')

    school = get_object_or_404(School, pk=school_id)

    if request.method == 'POST':
        school.name = request.POST.get('name', school.name).strip()
        school.establishment_year = request.POST.get('establishment_year') or None
        school.address = request.POST.get('address', school.address).strip()
        school.phone = request.POST.get('phone', school.phone).strip()
        school.email = request.POST.get('email', school.email).strip()
        school.website = request.POST.get('website', school.website).strip()
        school.principal_name = request.POST.get('principal_name', school.principal_name).strip()
        school.exam_head_name = request.POST.get('exam_head_name', school.exam_head_name).strip()
        school.grading_system = request.POST.get('grading_system', school.grading_system)
        school.subscription_start_date = request.POST.get('subscription_start_date') or None
        school.subscription_end_date = request.POST.get('subscription_end_date') or None

        if 'logo' in request.FILES:
            school.logo = request.FILES['logo']

        school.save()

        AuditLog.objects.create(
            school=school,
            user=request.user,
            action=AuditLog.Action.UPDATE,
            model_name='School',
            object_id=str(school.pk),
            object_repr=f"School: {school.name} — updated by Super Admin"
        )

        messages.success(request, f"School '{school.name}' updated successfully.")
        return redirect('super_schools')

    return render(request, 'schools/edit_school.html', {
        'school': school,
        'grading_system_choices': School.GradingSystem.choices
    })


@login_required
def subscription_expired(request):
    return render(request, 'schools/subscription_expired.html')
