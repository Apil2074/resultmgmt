"""
Schools App — Web views (Dashboard, School Profile, Academic Sessions)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout
from django.db.models import Count, Q
from django.db import transaction
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
        ctx['total_teachers'] = User.objects.filter(school=school, role=User.Role.TEACHER, is_active=True).count()
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
        from django.db.models import Avg
        import json
        
        gpa_data = {}
        perf_categories = {'Excellent': 0, 'Good': 0, 'Average': 0, 'Needs Improvement': 0}
        gpa_dist_stats = {
            '3.6-4.0': 0, '3.2-3.59': 0, '2.8-3.19': 0, '2.4-2.79': 0, '2.0-2.39': 0, '1.6-1.99': 0, '<1.6': 0
        }
        
        for result in results_qs:
            grade = result.final_grade or 'NG'
            gpa_data[grade] = gpa_data.get(grade, 0) + 1
            
            if result.overall_gpa is not None:
                g = float(result.overall_gpa)
                if g >= 3.6: 
                    perf_categories['Excellent'] += 1
                    gpa_dist_stats['3.6-4.0'] += 1
                elif g >= 3.2:
                    perf_categories['Good'] += 1
                    gpa_dist_stats['3.2-3.59'] += 1
                elif g >= 2.8: 
                    perf_categories['Good'] += 1
                    gpa_dist_stats['2.8-3.19'] += 1
                elif g >= 2.4: 
                    perf_categories['Average'] += 1
                    gpa_dist_stats['2.4-2.79'] += 1
                elif g >= 2.0: 
                    perf_categories['Average'] += 1
                    gpa_dist_stats['2.0-2.39'] += 1
                elif g >= 1.6: 
                    perf_categories['Needs Improvement'] += 1
                    gpa_dist_stats['1.6-1.99'] += 1
                else: 
                    perf_categories['Needs Improvement'] += 1
                    gpa_dist_stats['<1.6'] += 1

        # Calculate average GPA per class
        class_avg_data = {}
        class_stats = results_qs.values('student__class_obj__name', 'student__class_obj__numeric_level').annotate(
            avg_gpa=Avg('overall_gpa')
        ).order_by('student__class_obj__numeric_level', 'student__class_obj__name')
        
        for cs in class_stats:
            cname = cs['student__class_obj__name']
            agpa = cs['avg_gpa']
            if cname and agpa is not None:
                class_avg_data[cname] = round(float(agpa), 2)

        ctx['gpa_data'] = gpa_data
        ctx['perf_categories'] = perf_categories
        ctx['gpa_dist_stats_json'] = json.dumps(gpa_dist_stats)
        ctx['class_avg_data_json'] = json.dumps(class_avg_data)
        ctx['pass_fail_stats'] = {
            'passed': passed_results,
            'failed': total_results - passed_results,
        }

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

        if request.POST.get('remove_logo') == 'on':
            school.logo = None
        elif 'logo' in request.FILES:
            school.logo = request.FILES['logo']

        school.save()
        messages.success(request, 'School profile updated successfully.')
        return redirect('school_profile')

    return render(request, 'schools/profile.html', {
        'school': school,
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
            import_teachers = request.POST.get('import_teachers') == 'yes'
            if name:
                session, created = AcademicSession.objects.get_or_create(
                    school=school, name=name
                )
                if created:
                    messages.success(request, f'Session "{name}" created.')
                    if import_teachers:
                        active_session = school.get_active_session()
                        if active_session:
                            teachers = active_session.teachers.all()
                            if teachers.exists():
                                session.teachers.add(*teachers)
                                messages.success(request, f'Imported {teachers.count()} teachers from active session "{active_session.name}".')
                else:
                    messages.warning(request, f'Session "{name}" already exists.')
            else:
                messages.error(request, 'Session name is required.')

        elif action == 'edit':
            session_id = request.POST.get('session_id')
            new_name = request.POST.get('name', '').strip()
            if new_name:
                session = get_object_or_404(AcademicSession, pk=session_id, school=school)
                session.name = new_name
                session.save()
                messages.success(request, f'Session renamed to "{new_name}".')
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
                from django.db import transaction
                with transaction.atomic():
                    # 1. Create School
                    school = School.objects.create(
                        name=school_name,
                        establishment_year=int(est_year) if est_year else None,
                        address=address,
                        phone=phone,
                        email=email,
                        principal_name=principal,
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
                
                # 4. Send Welcome Notification
                welcome_html = f"""
                <div style="font-family: inherit; text-align: center; padding: 15px; border-radius: 8px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border: 1px solid #bbf7d0;">
                    <h3 style="color: #166534; margin-top: 0; font-weight: 700;">Welcome to ResultMgmt! 🚀</h3>
                    <p style="color: #15803d; font-size: 14px; margin-bottom: 5px;">We are thrilled to have <strong>{school.name}</strong> on board.</p>
                    <hr style="border: 0; border-top: 1px solid #86efac; margin: 12px 0;">
                    <p style="color: #166534; font-size: 13px; margin-bottom: 15px;">Get started by setting up your academic sessions, classes, and adding your teachers.</p>
                    <p style="color: #166534; font-size: 13px;">Your username: <strong>{user.username}</strong><br>Your password: <strong>{password}</strong></p>
                    <a href="http://127.0.0.1:8000/dashboard/" style="display: inline-block; padding: 8px 20px; background-color: #16a34a; color: white; text-decoration: none; border-radius: 20px; font-weight: 600; font-size: 13px; box-shadow: 0 4px 6px rgba(22, 163, 74, 0.2);">Go to Dashboard</a>
                </div>
                """
                from apps.accounts.models import Notification
                notification = Notification.objects.create(
                    title="Welcome to ResultMgmt! 🎉",
                    message=welcome_html,
                    sender=request.user
                )
                notification.recipients.add(user)
                
                # 5. Send Email
                from django.core.mail import send_mail
                from django.conf import settings
                from django.utils.html import strip_tags
                
                email_subject = "Welcome to ResultMgmt! 🎉"
                plain_message = strip_tags(welcome_html)
                from_email = getattr(settings, 'EMAIL_HOST_USER', 'noreply@resultmgmt.com')
                
                try:
                    send_mail(
                        subject=email_subject,
                        message=plain_message,
                        from_email=from_email,
                        recipient_list=[user.email],
                        fail_silently=True,
                        html_message=welcome_html
                    )
                except Exception as e:
                    pass
                
                messages.success(request, f"Successfully created school '{school.name}' and admin user '{user.username}'.")
                return redirect('super_schools')
            except Exception as e:
                messages.error(request, f"Error creating school and admin: {str(e)}")
                
    return render(request, 'schools/create_school_and_admin.html')


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
        school.subscription_start_date = request.POST.get('subscription_start_date') or None
        school.subscription_end_date = request.POST.get('subscription_end_date') or None

        if request.POST.get('remove_logo') == 'on':
            school.logo = None
        elif 'logo' in request.FILES:
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
        
    })


@login_required
def reset_school_admin_password(request, school_id):
    """Super Admin — force-reset the password of a school admin account."""
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Only Super Admins can reset passwords.")
        return redirect('dashboard')

    school = get_object_or_404(School, pk=school_id)

    # Get the selected admin_id from GET/POST, or fall back to first admin
    admin_id = request.POST.get('admin_id') or request.GET.get('admin_id')
    all_admins = list(
        school.users.filter(role=User.Role.SCHOOL_ADMIN).order_by('date_joined')
    )

    if not all_admins:
        messages.error(request, f"No School Admin account found for '{school.name}'.")
        return redirect('super_schools')

    # Select the right admin
    admin_user = None
    if admin_id:
        for a in all_admins:
            if str(a.pk) == str(admin_id):
                admin_user = a
                break
    if admin_user is None:
        admin_user = all_admins[0]

    if request.method == 'POST':
        new_password     = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not new_password:
            messages.error(request, 'Password cannot be empty.')
        elif len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        elif new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
        else:
            # Use update_fields so the custom save() only touches the password column
            admin_user.set_password(new_password)
            admin_user.save(update_fields=['password', 'updated_at'])

            AuditLog.objects.create(
                school=school,
                user=request.user,
                action=AuditLog.Action.UPDATE,
                model_name='User',
                object_id=str(admin_user.pk),
                object_repr=(
                    f"Password reset for admin '{admin_user.username}' "
                    f"of school '{school.name}' by Super Admin"
                ),
            )

            messages.success(
                request,
                f"Password for '{admin_user.username}' ({school.name}) reset successfully.",
            )
            return redirect('super_schools')

    return render(request, 'schools/reset_admin_password.html', {
        'school': school,
        'admin_user': admin_user,
        'all_admins': all_admins,
    })


@login_required
def subscription_expired(request):
    return render(request, 'schools/subscription_expired.html')

# -----------------------------------------------------------------------------
# SUPPORT TICKETS
# -----------------------------------------------------------------------------

@login_required
def support_ticket_list(request):
    """School Admin view to list their tickets and create new ones."""
    if not request.user.can_manage_school:
        messages.error(request, "Access denied. Only School Admins can manage tickets.")
        return redirect('dashboard')
    
    from apps.schools.models import SupportTicket
    
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        if subject and message:
            ticket = SupportTicket.objects.create(
                school=request.user.school,
                created_by=request.user,
                subject=subject
            )
            from apps.schools.models import TicketMessage
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=message,
                attachment=request.FILES.get('attachment')
            )
            messages.success(request, 'Support ticket created successfully.')
            return redirect('support_ticket_list')
        else:
            messages.error(request, 'Subject and message are required.')

    tickets = SupportTicket.objects.filter(school=request.user.school)
    return render(request, 'schools/support/ticket_list.html', {
        'tickets': tickets
    })


@login_required
def support_ticket_detail(request, ticket_id):
    """School Admin view to see a ticket thread and reply."""
    from apps.schools.models import SupportTicket, TicketMessage
    from django.shortcuts import get_object_or_404
    
    ticket = get_object_or_404(SupportTicket, pk=ticket_id, school=request.user.school)
    
    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        if message:
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=message,
                attachment=request.FILES.get('attachment')
            )
            messages.success(request, 'Reply sent successfully.')
            return redirect('support_ticket_detail', ticket_id=ticket.pk)
            
    return render(request, 'schools/support/ticket_detail.html', {
        'ticket': ticket,
        'messages': ticket.messages.all()
    })


@login_required
def super_ticket_list(request):
    """Super Admin view to list all tickets."""
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
        
    from apps.schools.models import SupportTicket
    
    status_filter = request.GET.get('status')
    tickets = SupportTicket.objects.all().select_related('school')
    
    if status_filter:
        tickets = tickets.filter(status=status_filter)
        
    return render(request, 'schools/super_ticket_list.html', {
        'tickets': tickets,
        'current_status': status_filter
    })


@login_required
def super_ticket_detail(request, ticket_id):
    """Super Admin view to read and reply to a specific ticket."""
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
        
    from apps.schools.models import SupportTicket, TicketMessage
    from django.shortcuts import get_object_or_404
    
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'reply':
            message = request.POST.get('message', '').strip()
            if message:
                TicketMessage.objects.create(
                    ticket=ticket,
                    sender=request.user,
                    message=message,
                    attachment=request.FILES.get('attachment')
                )
                messages.success(request, 'Reply sent successfully.')
                
        elif action == 'change_status':
            new_status = request.POST.get('status')
            if new_status in dict(SupportTicket.Status.choices):
                ticket.status = new_status
                ticket.save()
                messages.success(request, f'Ticket status changed to {new_status}.')
                
        return redirect('super_ticket_detail', ticket_id=ticket.pk)
        
    return render(request, 'schools/super_ticket_detail.html', {
        'ticket': ticket,
        'messages': ticket.messages.all(),
        'status_choices': SupportTicket.Status.choices
    })

@login_required
def super_schools(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    schools = School.objects.all().order_by('-created_at')
    return render(request, 'schools/super_schools_list.html', {'schools': schools})

@login_required
def super_notifications(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    from apps.accounts.models import User, Notification
    school_admins = User.objects.filter(role=User.Role.SCHOOL_ADMIN, is_active=True)
    
    # Fetch recent notifications sent by this admin
    recent_notifications = Notification.objects.filter(sender=request.user).order_by('-created_at')[:10]
    
    return render(request, 'schools/super_notifications.html', {
        'school_admins': school_admins,
        'recent_notifications': recent_notifications
    })


@login_required
def teacher_notifications(request):
    if not request.user.can_manage_school():
        messages.error(request, "Access denied. School Admins only.")
        return redirect('dashboard')
    from apps.accounts.models import User, Notification
    teachers = User.objects.filter(role=User.Role.TEACHER, school=request.user.school, is_active=True)
    
    # Fetch recent notifications sent by this admin
    recent_notifications = Notification.objects.filter(sender=request.user).order_by('-created_at')[:10]
    
    return render(request, 'schools/teacher_notifications.html', {
        'teachers': teachers,
        'recent_notifications': recent_notifications
    })

@login_required
def super_subscriptions(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    return render(request, 'schools/super_subscriptions.html')

@login_required
def super_analytics(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
        
    import json
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    from django.utils import timezone
    from apps.schools.models import School
    from apps.students.models import Student
    from apps.exams.models import Exam
    from apps.accounts.models import User

    # Basic KPIs
    total_schools = School.objects.count()
    active_schools = School.objects.filter(is_active=True).count()
    inactive_schools = total_schools - active_schools
    
    total_students = Student.objects.filter(is_active=True).count()
    total_exams = Exam.objects.count()
    total_teachers = User.objects.filter(role=User.Role.TEACHER).count()
    
    # Growth Data (Schools registered per month for current year)
    current_year = timezone.now().year
    
    growth_qs = School.objects.filter(created_at__year=current_year)\
        .annotate(month=TruncMonth('created_at'))\
        .values('month')\
        .annotate(count=Count('id'))\
        .order_by('month')
        
    months_map = {i: 0 for i in range(1, 13)}
    for entry in growth_qs:
        if entry['month']:
            months_map[entry['month'].month] = entry['count']
            
    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    growth_data = [months_map[i] for i in range(1, 13)]
    
    context = {
        'total_schools': total_schools,
        'active_schools': active_schools,
        'inactive_schools': inactive_schools,
        'total_students': total_students,
        'total_exams': total_exams,
        'total_teachers': total_teachers,
        'months_labels_json': json.dumps(months_labels),
        'growth_data_json': json.dumps(growth_data),
    }

    return render(request, 'schools/super_analytics.html', context)

@login_required
def super_reports(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    return render(request, 'schools/super_reports.html')

@login_required
def super_settings(request):
    if not request.user.is_super_admin:
        messages.error(request, "Access denied. Super Admin only.")
        return redirect('dashboard')
    return render(request, 'schools/super_settings.html')
