"""
Teachers App — Web views
"""
import io
import json
import openpyxl
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db import transaction

from apps.accounts.models import User
from apps.classes.models import Class
from apps.subjects.models import Subject
from .models import Teacher, TeacherSubject


@login_required
def teacher_list(request):
    """List all teachers in the school."""
    school = request.user.school
    
    if request.method == 'POST':
        if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
            messages.error(request, 'Access denied.')
            return redirect('teacher_list')

    active_session = school.get_active_session()
    
    teachers_qs = Teacher.objects.filter(school=school).select_related('user').prefetch_related('subject_assignments')
    if active_session:
        teachers_qs = teachers_qs.filter(sessions=active_session)
    
    def get_sort_key(t):
        try:
            val = float(t.sn) if t.sn else float('inf')
        except ValueError:
            import re
            nums = re.findall(r'\d+', t.sn)
            val = float(nums[0]) if nums else float('inf')
        return (val, t.name)
        
    teachers = sorted(teachers_qs, key=get_sort_key)
    
    return render(request, 'teachers/list.html', {
        'teachers': teachers
    })


@login_required
def teacher_create(request):
    """Create a new teacher manually."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    if request.method == 'POST':
        sn = request.POST.get('sn', '').strip()
        name = request.POST.get('name', '').strip()
        contact = request.POST.get('contact_number', '').strip()
        dob = request.POST.get('date_of_birth') or None
        email = request.POST.get('email', '').strip() or None

        if email and Teacher.objects.filter(email__iexact=email).exists():
            messages.error(request, f'The email {email} is already in use by another teacher.')
            return render(request, 'teachers/form.html')

        photo = None
        if 'photo' in request.FILES:
            from django.core.exceptions import ValidationError
            from core.security import validate_image_upload
            try:
                validate_image_upload(request.FILES['photo'])
                photo = request.FILES['photo']
            except ValidationError as e:
                messages.error(request, str(e.message))
                return render(request, 'teachers/form.html')

        teacher = Teacher.objects.create(
            school=school,
            sn=sn,
            name=name,
            contact_number=contact,
            date_of_birth=dob,
            email=email,
            photo=photo
        )
        active_session = school.get_active_session()
        if active_session:
            teacher.sessions.add(active_session)
            
        messages.success(request, f'Teacher {name} added successfully.')
        return redirect('teacher_list')

    return render(request, 'teachers/form.html')


@login_required
def teacher_detail(request, pk):
    """View teacher profile."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    teacher = get_object_or_404(Teacher, pk=pk, school=school)
    
    # Get active session assignments
    active_session = school.get_active_session() if school else None
    assignments = teacher.subject_assignments.select_related('subject', 'subject__class_obj')
    if active_session:
        assignments = assignments.filter(subject__class_obj__session=active_session)
        
    return render(request, 'teachers/detail.html', {
        'teacher': teacher,
        'assignments': assignments,
        'active_session': active_session
    })


@login_required
def teacher_edit(request, pk):
    """Edit teacher details."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    teacher = get_object_or_404(Teacher, pk=pk, school=school)

    if request.method == 'POST':
        teacher.sn = request.POST.get('sn', teacher.sn).strip()
        teacher.name = request.POST.get('name', teacher.name).strip()
        teacher.contact_number = request.POST.get('contact_number', teacher.contact_number).strip()
        dob = request.POST.get('date_of_birth')
        teacher.date_of_birth = dob if dob else None
        
        email = request.POST.get('email', '').strip() or None
        if email and email != teacher.email:
            if Teacher.objects.exclude(pk=teacher.pk).filter(email__iexact=email).exists():
                messages.error(request, f'The email {email} is already in use by another teacher.')
                return render(request, 'teachers/form.html', {'teacher': teacher})
        teacher.email = email

        if 'photo' in request.FILES:
            from django.core.exceptions import ValidationError
            from core.security import validate_image_upload
            try:
                validate_image_upload(request.FILES['photo'])
                teacher.photo = request.FILES['photo']
            except ValidationError as e:
                messages.error(request, str(e.message))
                return render(request, 'teachers/form.html', {'teacher': teacher})
        elif request.POST.get('remove_photo'):
            if teacher.photo:
                teacher.photo.delete(save=False)
                teacher.photo = None

        teacher.save()
        messages.success(request, f'Teacher {teacher.name} updated successfully.')
        return redirect('teacher_list')

    return render(request, 'teachers/form.html', {'teacher': teacher})


@login_required
def teacher_delete(request, pk):
    """Delete a teacher."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    teacher = get_object_or_404(Teacher, pk=pk, school=school)
    
    if request.method == 'POST':
        name = teacher.name
        # Delete associated user account if it exists
        if teacher.user:
            teacher.user.delete()
        teacher.delete()
        messages.success(request, f'Teacher {name} permanently deleted.')
        return redirect('teacher_list')
        
    return redirect('teacher_list')


@login_required
def teacher_bulk_delete(request):
    """Bulk delete teachers."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    if request.method == 'POST':
        teacher_ids = request.POST.getlist('teacher_ids')
        if teacher_ids:
            teachers = Teacher.objects.filter(pk__in=teacher_ids, school=school)
            deleted_count = 0
            for teacher in teachers:
                if teacher.user:
                    teacher.user.delete()
                teacher.delete()
                deleted_count += 1
            if deleted_count > 0:
                messages.success(request, f'Successfully deleted {deleted_count} teacher(s).')
            else:
                messages.warning(request, 'No teachers were deleted.')
        else:
            messages.warning(request, 'No teachers were selected for deletion.')
            
    return redirect('teacher_list')


@login_required
def teacher_import(request):
    """Import teachers from Excel."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            created = 0
            errors = []
            
            from django.db import transaction
            
            with transaction.atomic():
                for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    if not row[0] and not row[1]:
                        continue
                    try:
                        sn = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ''
                        name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
                        if not name:
                            continue
                            
                        contact = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ''
                        
                        dob = None
                        dob_val = row[3] if len(row) > 3 else None
                        if dob_val is not None:
                            if isinstance(dob_val, (datetime.date, datetime.datetime)):
                                dob = dob_val if isinstance(dob_val, datetime.date) else dob_val.date()
                            else:
                                dob_str = str(dob_val).strip()
                                if dob_str:
                                    date_formats = ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d')
                                    for fmt in date_formats:
                                        try:
                                            dob = datetime.datetime.strptime(dob_str, fmt).date()
                                            break
                                        except ValueError:
                                            continue

                        teacher = Teacher.objects.create(
                            school=school,
                            sn=sn,
                            name=name,
                            contact_number=contact,
                            date_of_birth=dob
                        )
                        active_session = school.get_active_session()
                        if active_session:
                            teacher.sessions.add(active_session)
                        created += 1
                    except Exception as e:
                        errors.append(f'Row {row_num}: {str(e)}')
                        
                if errors:
                    transaction.set_rollback(True)
                    messages.error(request, f'Import failed due to errors. No teachers were imported.')
                    for err in errors[:5]:
                        messages.error(request, err)
                    if len(errors) > 5:
                        messages.error(request, f'...and {len(errors) - 5} more errors.')
                else:
                    messages.success(request, f'{created} teachers imported successfully.')

        except Exception as e:
            messages.error(request, f'Failed to read Excel file: {str(e)}')

        return redirect('teacher_list')

    return render(request, 'teachers/import.html')


@login_required
def teacher_import_template(request):
    """Download blank Excel template for teacher import."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Teachers'
    
    from openpyxl.styles import Font, PatternFill
    headers = ['SN', 'Teacher Name*', 'Contact Number', 'Date of Birth']
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='F59E0B', end_color='F59E0B', fill_type='solid')
    
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 25

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="teacher_import_template.xlsx"'
    wb.save(response)
    return response


@login_required
def teacher_create_user(request, pk):
    """Auto-generate a User account for the teacher."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    teacher = get_object_or_404(Teacher, pk=pk, school=school)
    
    if request.method == 'POST':
        if teacher.user:
            messages.warning(request, f'Teacher {teacher.name} already has an account.')
            return redirect('teacher_list')
            
        import re
        # Generate base username
        base_username = re.sub(r'[^a-zA-Z0-9]', '', teacher.name.lower())
        if teacher.sn:
            username = f"{base_username}{teacher.sn}"
        else:
            username = base_username
            
        # Ensure uniqueness
        original_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{original_username}{counter}"
            counter += 1
        import secrets
        # Generate an 8-character password
        password = secrets.token_urlsafe(6)

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=teacher.name,
                    role=User.Role.TEACHER,
                    school=school
                )
                teacher.user = user
                teacher.save()

            messages.success(request, f'Account created for {teacher.name}. Username: {username}. Temporary Password: {password} (Please copy this password now, it will not be shown again!)')
            # In a real system, you'd likely email it or show it ONCE on a dedicated screen, not in the session flash messages.
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')

        return redirect('teacher_list')

    return redirect('teacher_list')


@login_required
def teacher_reset_password(request, pk):
    """Reset password for a teacher's User account."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    teacher = get_object_or_404(Teacher, pk=pk, school=school)
    
    if request.method == 'POST':
        if not teacher.user:
            messages.error(request, 'This teacher does not have an account.')
            return redirect('teacher_list')
        import secrets
        # Generate an 8-character password
        password = secrets.token_urlsafe(6)

        teacher.user.set_password(password)
        teacher.user.save()
        messages.success(request, f'Password reset for {teacher.name}. New password: {password} (Please copy this password now!)')
    return redirect('teacher_list')


@login_required
def teacher_send_password_reset(request, pk):
    """Send a password reset email to the teacher."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    teacher = get_object_or_404(Teacher, pk=pk, school=school)
    
    if request.method == 'POST':
        if not teacher.email:
            messages.error(request, 'This teacher does not have an email address set.')
            return redirect(request.META.get('HTTP_REFERER', 'teacher_list'))
            
        import secrets
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.urls import reverse
        from django.core.mail import send_mail
        from django.conf import settings
        
        try:
            if not teacher.user:
                # Auto-create user so they can receive the reset link and log in
                username_base = teacher.email.split('@')[0]
                user = User.objects.create_user(
                    username=f"{username_base}_{teacher.pk}_{secrets.token_hex(2)}",
                    email=teacher.email,
                    password=secrets.token_urlsafe(16),
                    first_name=teacher.name,
                    role=User.Role.TEACHER,
                    school=school
                )
                teacher.user = user
                teacher.save()
            else:
                # Ensure email matches
                if teacher.user.email != teacher.email:
                    teacher.user.email = teacher.email
                    teacher.user.save()
                    
            uid = urlsafe_base64_encode(force_bytes(teacher.user.pk))
            token = default_token_generator.make_token(teacher.user)
            reset_url = request.build_absolute_uri(
                reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            )
            
            send_mail(
                subject='Password Reset Request',
                message=f'Hello {teacher.name},\n\nPlease click the link below to set your new password:\n{reset_url}\n\nThis link is valid for a limited time.\n\nThank you.',
                from_email=getattr(settings, 'EMAIL_HOST_USER', None) or "noreply@rms.local",
                recipient_list=[teacher.email],
                fail_silently=False,
            )
            messages.success(request, f'Password reset email sent to {teacher.email}.')
            
            # Log action
            from apps.audit.models import AuditLog
            AuditLog.log_action(
                user=request.user,
                action='PASSWORD_RESET_SENT',
                model_name='Teacher',
                object_id=teacher.pk,
                details=f'Sent password reset email to {teacher.email}'
            )
        except Exception as e:
            messages.error(request, f'Error sending password reset email: {str(e)}')

    return redirect(request.META.get('HTTP_REFERER', 'teacher_list'))


@login_required
def teacher_subject_map(request, pk):
    """UI to map subjects to a teacher."""
    school = request.user.school
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    teacher = get_object_or_404(Teacher, pk=pk, school=school)
    
    if request.method == 'POST':
        subject_ids = request.POST.getlist('subject_ids')
        
        # Only map selected subjects, delete unselected ones
        TeacherSubject.objects.filter(teacher=teacher).exclude(subject_id__in=subject_ids).delete()
        
        for sub_id in subject_ids:
            TeacherSubject.objects.get_or_create(
                teacher=teacher,
                subject_id=sub_id
            )
            
        messages.success(request, f'Subjects mapped successfully for {teacher.name}.')
        return redirect('teacher_list')
        
    active_session = school.get_active_session() if school else None
    classes_qs = Class.objects.filter(school=school)
    if active_session:
        classes_qs = classes_qs.filter(session=active_session)
        
    classes = list(classes_qs.prefetch_related('subjects'))
    mapped_subject_ids = list(teacher.subject_assignments.values_list('subject_id', flat=True))
    
    all_other_assignments = TeacherSubject.objects.filter(
        subject__class_obj__school=school
    ).exclude(teacher=teacher).select_related('teacher')
    
    other_assignments_dict = {ta.subject_id: ta.teacher.name for ta in all_other_assignments}

    for cls in classes:
        for sub in cls.subjects.all():
            sub.is_mapped_to_current = sub.id in mapped_subject_ids
            sub.other_teacher_name = other_assignments_dict.get(sub.id)
    
    return render(request, 'teachers/subject_map.html', {
        'teacher': teacher,
        'classes': classes,
    })


# ---------------------------------------------------------
# TEACHER PORTAL VIEWS
# ---------------------------------------------------------

@login_required
def teacher_dashboard(request):
    """Dashboard specifically for users with the TEACHER role."""
    if not request.user.is_teacher:
        return redirect('dashboard')
        
    try:
        teacher = request.user.teacher_profile
    except Teacher.DoesNotExist:
        messages.error(request, 'Your account is not linked to any teacher profile.')
        return render(request, 'teachers/teacher_portal/dashboard.html', {'error': True})
        
    active_session = request.user.school.get_active_session() if hasattr(request.user, 'school') and request.user.school else None
    
    assignments = TeacherSubject.objects.filter(
        teacher=teacher
    ).select_related('subject', 'subject__class_obj')
    
    if active_session:
        assignments = assignments.filter(subject__class_obj__session=active_session)
    
    # Group by class
    classes_dict = {}
    class_ids = set()
    for assignment in assignments:
        cls = assignment.subject.class_obj
        if cls not in classes_dict:
            classes_dict[cls] = []
        classes_dict[cls].append(assignment.subject)
        class_ids.add(cls.id)

    classes_info = []
    from apps.exams.models import ExamClass
    for cls, subjects in classes_dict.items():
        latest_ec = ExamClass.objects.filter(
            class_obj=cls, 
            exam__status='DRAFT'
        )
        if active_session:
            latest_ec = latest_ec.filter(exam__session=active_session)
        latest_ec = latest_ec.order_by('-exam__created_at').first()
        
        classes_info.append({
            'class_obj': cls,
            'subjects': subjects,
            'latest_exam_id': latest_ec.exam_id if latest_ec else None
        })

        
    # Calculate KPIs
    from apps.students.models import Student
    from apps.exams.models import Exam
    from apps.results.models import StudentResult
    from django.db.models import Avg

    total_classes = len(classes_dict)
    total_subjects = assignments.count()
    primary_subject = assignments.first().subject.name if assignments.exists() else "None"
    
    total_students = Student.objects.filter(class_obj__id__in=class_ids, is_active=True).count()
    
    # Exams related to the active session for these classes
    related_exams = Exam.objects.filter(session=active_session, exam_classes__class_obj__id__in=class_ids).distinct()
    
    # Published vs Pending logic
    published_exams = related_exams.filter(status='PUBLISHED').count()
    total_exams = related_exams.count()
    published_percentage = int((published_exams / total_exams * 100)) if total_exams > 0 else 0
    
    pending_marks = total_exams - published_exams  # Simplified pending logic
    
    # Average GPA
    avg_gpa_dict = StudentResult.objects.filter(student__class_obj__id__in=class_ids).aggregate(Avg('overall_gpa'))
    avg_gpa = round(avg_gpa_dict['overall_gpa__avg'] or 0.0, 2)
    
    # Grade Distribution
    from django.db.models import Count
    import json
    grade_counts = StudentResult.objects.filter(student__class_obj__id__in=class_ids).values('final_grade').annotate(count=Count('id')).order_by('final_grade')
    
    grades = []
    counts = []
    for gc in grade_counts:
        grade = gc['final_grade']
        if grade == '':
            continue
        grades.append(grade)
        counts.append(gc['count'])
        
    grade_labels_json = json.dumps(grades)
    grade_data_json = json.dumps(counts)

    # Top Performers per Class and Subject
    from django.db.models.functions import Coalesce
    from django.db.models import DecimalField
    from apps.marks.models import MarkEntry
    
    top_performers = []
    for cls_obj, subjects in classes_dict.items():
        for subject in subjects:
            top_marks = MarkEntry.objects.filter(
                student__class_obj=cls_obj, 
                subject=subject,
                session=active_session
            ).annotate(
                total_marks=Coalesce('theory_obtained', 0.0, output_field=DecimalField()) + Coalesce('internal_obtained', 0.0, output_field=DecimalField())
            ).order_by('-total_marks')[:3]

            leaders = []
            for idx, mark in enumerate(top_marks):
                leaders.append({
                    'rank': idx + 1,
                    'student': mark.student,
                    'score': float(mark.total_marks) if mark.total_marks else 0.0
                })
            
            if leaders:
                top_performers.append({
                    'class': cls_obj,
                    'subject': subject,
                    'leaders': leaders
                })
    
    # Sort top performers by class level, then subject
    top_performers.sort(key=lambda x: (x['class'].numeric_level, x['class'].name, x['subject'].name))
        
    return render(request, 'teachers/teacher_portal/dashboard.html', {
        'teacher': teacher,
        'classes_dict': classes_dict,
        'classes_info': classes_info,
        'total_classes': total_classes,
        'total_students': total_students,
        'total_subjects': total_subjects,
        'primary_subject': primary_subject,
        'pending_marks': pending_marks,
        'published_percentage': published_percentage,
        'avg_gpa': avg_gpa,
        'grade_labels_json': grade_labels_json,
        'grade_data_json': grade_data_json,
        'top_performers': top_performers,
    })
