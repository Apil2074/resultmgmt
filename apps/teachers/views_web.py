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
    
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
        
    teachers_qs = Teacher.objects.filter(school=school).select_related('user').prefetch_related('subject_assignments')
    
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

        Teacher.objects.create(
            school=school,
            sn=sn,
            name=name,
            contact_number=contact,
            date_of_birth=dob,
            photo=photo
        )
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
                                for fmt in ('%Y-%m-%d',):
                                    try:
                                        dob = datetime.datetime.strptime(dob_str, fmt).date()
                                        break
                                    except ValueError:
                                        continue

                    Teacher.objects.create(
                        school=school,
                        sn=sn,
                        name=name,
                        contact_number=contact,
                        date_of_birth=dob
                    )
                    created += 1
                except Exception as e:
                    errors.append(f'Row {row_num}: {str(e)}')

            messages.success(request, f'{created} teachers imported successfully.')
            if errors:
                for err in errors[:5]:
                    messages.warning(request, err)

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
        # SECURITY: Generate a stronger 16-character password instead of 8
        password = secrets.token_urlsafe(16)

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

            # SECURITY: Remove raw password from flash message!
            messages.success(request, f'Account created for {teacher.name}. Username: {username}. Provide the temporary password securely.')
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
        # SECURITY: Generate a stronger 16-character password instead of 8
        password = secrets.token_urlsafe(16)

        teacher.user.set_password(password)
        teacher.user.save()

        # SECURITY: Remove raw password from flash message!
        messages.success(request, f'Password reset for {teacher.name}. Provide the new temporary password securely.')
        # In a real system, you'd likely email it or show it ONCE on a dedicated screen, not in the session flash messages.

    return redirect('teacher_list')


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
    for assignment in assignments:
        cls = assignment.subject.class_obj
        if cls not in classes_dict:
            classes_dict[cls] = []
        classes_dict[cls].append(assignment.subject)
        
    return render(request, 'teachers/teacher_portal/dashboard.html', {
        'teacher': teacher,
        'classes_dict': classes_dict
    })
