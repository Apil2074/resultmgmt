"""
Students App — Web views with Excel import/export
"""
import io
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import Student
from core.security import safe_redirect_url, validate_image_upload

logger = logging.getLogger(__name__)



@login_required
def student_list(request):
    school = request.user.school
    active_session = school.get_active_session() if school else None
    students = Student.objects.filter(school=school, is_active=True)
    if active_session:
        students = students.filter(class_obj__session=active_session)
    students = students.select_related(
        'class_obj', 'class_obj__session'
    )

    # Search and filter
    q = request.GET.get('q', '')
    class_id = request.GET.get('class_id', '')
    if q:
        students = students.filter(
            name__icontains=q
        ) | students.filter(roll_number__icontains=q)
    if class_id:
        students = students.filter(class_obj_id=class_id)

    # Convert to list and apply natural sorting (class, then roll number naturally)
    students_list = list(students)
    students_list.sort(key=lambda s: (
        s.class_obj.numeric_level,
        s.class_obj.name,
        s.class_obj.section,
        len(s.roll_number),
        s.roll_number
    ))

    from apps.classes.models import Class
    classes_qs = Class.objects.filter(school=school)
    if active_session:
        classes_qs = classes_qs.filter(session=active_session)
    classes = list(classes_qs)

    return render(request, 'students/list.html', {
        'students': students_list,
        'classes': classes,
        'q': q,
        'class_id': class_id,
    })


@login_required
def student_create(request):
    if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('student_list')
    school = request.user.school
    active_session = school.get_active_session() if school else None
    from apps.classes.models import Class
    classes = Class.objects.filter(school=school)
    if active_session:
        classes = classes.filter(session=active_session)

    if request.method == 'POST':
        Student.objects.create(
            school=school,
            class_obj_id=request.POST.get('class_id'),
            roll_number=request.POST.get('roll_number'),
            name=request.POST.get('name'),
            gender=request.POST.get('gender'),
            registration_number=request.POST.get('registration_number', ''),
            symbol_number=request.POST.get('symbol_number', ''),
            date_of_birth=request.POST.get('date_of_birth') or None,
            parent_name=request.POST.get('parent_name', ''),
            contact_number=request.POST.get('contact_number', ''),
            address=request.POST.get('address', ''),
            photo=request.FILES.get('photo'),
        )
        messages.success(request, 'Student added successfully.')
        return redirect('student_list')

    return render(request, 'students/form.html', {'classes': classes})


@login_required
def student_detail(request, pk):
    school = request.user.school
    student = get_object_or_404(Student, pk=pk, school=school)
    from apps.results.models import StudentResult
    results = StudentResult.objects.filter(
        student=student
    ).select_related('exam').order_by('-exam__start_date')
    return render(request, 'students/detail.html', {
        'student': student,
        'results': results,
    })


@login_required
def student_edit(request, pk):
    if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('student_list')
    school = request.user.school
    active_session = school.get_active_session() if school else None
    student = get_object_or_404(Student, pk=pk, school=school)
    from apps.classes.models import Class
    classes = Class.objects.filter(school=school)
    if active_session:
        classes = classes.filter(session=active_session)

    if request.method == 'POST':
        student.name = request.POST.get('name', student.name)
        student.roll_number = request.POST.get('roll_number', student.roll_number)
        student.registration_number = request.POST.get('registration_number', '')
        student.symbol_number = request.POST.get('symbol_number', '')
        student.gender = request.POST.get('gender', student.gender)
        student.parent_name = request.POST.get('parent_name', '')
        student.contact_number = request.POST.get('contact_number', '')
        student.address = request.POST.get('address', '')
        dob = request.POST.get('date_of_birth')
        student.date_of_birth = dob if dob else None
        if 'photo' in request.FILES:
            from django.core.exceptions import ValidationError
            try:
                validate_image_upload(request.FILES['photo'])
                student.photo = request.FILES['photo']
            except ValidationError as e:
                messages.error(request, str(e.message))
                return render(request, 'students/form.html', {'student': student, 'classes': classes})
        elif request.POST.get('remove_photo'):
            if student.photo:
                student.photo.delete(save=False)
                student.photo = None

        student.save()
        messages.success(request, 'Student updated.')

        # SECURITY: Validate next= to prevent open redirect attacks
        next_url = safe_redirect_url(
            request.POST.get('next') or request.GET.get('next'), request
        )
        return redirect(next_url or ('student_detail', [student.pk]))

    return render(request, 'students/form.html', {
        'student': student,
        'classes': classes,
    })


@login_required
def student_delete(request, pk):
    if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('student_list')
    school = request.user.school
    student = get_object_or_404(Student, pk=pk, school=school)
    if request.method == 'POST':
        student_name = student.name
        student.delete()
        messages.success(request, f'Student {student_name} permanently deleted.')

        # SECURITY: Validate next= to prevent open redirect attacks
        next_url = safe_redirect_url(
            request.POST.get('next') or request.GET.get('next'), request
        )
        return redirect(next_url or 'student_list')
    return render(request, 'students/confirm_delete.html', {'student': student})


def parse_class_and_section(class_str):
    class_str = class_str.strip()
    if not class_str:
        return None, None
    import re
    # Match Class 10 A, Class 10 - A, Class 10A, Grade 9 B, etc.
    match = re.search(r'^(.*?)\s*[- ]\s*([a-zA-Z])$', class_str)
    if match:
        return match.group(1).strip(), match.group(2).strip().upper()
    return class_str, ''


@login_required
def student_import(request):
    if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('student_list')
    """Import students from Excel."""
    school = request.user.school
    active_session = school.get_active_session() if school else None
    from apps.classes.models import Class
    classes = Class.objects.filter(school=school)
    if active_session:
        classes = classes.filter(session=active_session)

    if request.method == 'POST' and request.FILES.get('excel_file'):
        import openpyxl
        import datetime
        from django.utils import timezone
        
        excel_file = request.FILES['excel_file']
        class_id = request.POST.get('class_id')
        dropdown_cls = Class.objects.filter(pk=class_id, school=school).first() if class_id else None

        active_session = school.get_active_session()
        if not active_session:
            from apps.schools.models import AcademicSession
            active_session, _ = AcademicSession.objects.get_or_create(
                school=school,
                is_active=True,
                defaults={'name': str(timezone.now().year)}
            )

        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            created = 0
            errors = []

            # Track next roll number per class (class pk -> next int)
            # Roll numbers are sequential starting from 1 per class, independent of Excel SN
            class_roll_counters = {}

            def get_next_roll(cls_obj):
                """Return the next sequential roll number for this class."""
                if cls_obj.pk not in class_roll_counters:
                    # Seed from existing students in this class
                    existing = Student.objects.filter(
                        school=school, class_obj=cls_obj
                    ).values_list('roll_number', flat=True)
                    max_roll = 0
                    for r in existing:
                        try:
                            max_roll = max(max_roll, int(r))
                        except (ValueError, TypeError):
                            pass
                    class_roll_counters[cls_obj.pk] = max_roll
                class_roll_counters[cls_obj.pk] += 1
                return str(class_roll_counters[cls_obj.pk])

            for row_num, row in enumerate(ws.iter_rows(min_row=1, values_only=True), start=1):
                if not row[0]:
                    continue
                # Skip the title row or header row
                sn_val = str(row[0]).strip().upper()
                if sn_val.startswith('CLASS:') or sn_val == 'SN*' or sn_val == 'SN':
                    continue

                try:
                    # Column 0 is SN (serial number)
                    # Symbol No
                    symbol = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
                    # REG NO
                    reg_num = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ''
                    # Name
                    name = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ''
                    if not name:
                        raise ValueError("Student name is required.")
                    
                    # Gender
                    gender_raw = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ''
                    gender = None
                    if gender_raw:
                        gen_cap = gender_raw.strip().upper()
                        if gen_cap in ('M', 'MALE'):
                            gender = 'M'
                        elif gen_cap in ('F', 'FEMALE'):
                            gender = 'F'
                        elif gen_cap in ('O', 'OTHER'):
                            gender = 'O'
                    
                    # Class is taken from the dropdown
                    cls = dropdown_cls
                    if not cls:
                        raise ValueError("No class specified for this import.")
                    
                    # DOB (Excel has BS date, convert to AD and save both)
                    dob_ad = None
                    dob_bs_str = ""
                    dob_val = row[5] if len(row) > 5 else None
                    
                    student_obj = None
                    if reg_num:
                        student_obj = Student.objects.filter(registration_number=reg_num, school=school).first()

                    if dob_val is not None:
                        import nepali_datetime
                        if isinstance(dob_val, (datetime.date, datetime.datetime)):
                            y, m, d = dob_val.year, dob_val.month, dob_val.day
                            dob_bs_str = f"{y:04d}-{m:02d}-{d:02d}"
                            try:
                                np_date = nepali_datetime.date(y, m, d)
                                dob_ad = np_date.to_datetime_date()
                            except Exception:
                                pass
                        else:
                            dob_str = str(dob_val).strip()
                            if dob_str:
                                dob_bs_str = dob_str
                                try:
                                    parts = [int(p) for p in dob_str.split('-')]
                                    if len(parts) == 3:
                                        y, m, d = parts
                                        np_date = nepali_datetime.date(y, m, d)
                                        dob_ad = np_date.to_datetime_date()
                                except Exception:
                                    pass

                    # Check if student already exists by symbol/reg number to avoid duplicate roll assignment
                    existing_student = None
                    if symbol:
                        existing_student = Student.objects.filter(
                            school=school, class_obj=cls, symbol_number=symbol
                        ).first()
                    if not existing_student and reg_num:
                        existing_student = Student.objects.filter(
                            school=school, class_obj=cls, registration_number=reg_num
                        ).first()

                    if existing_student:
                        # Update existing student, preserve their existing roll number
                        existing_student.name = name
                        existing_student.registration_number = reg_num
                        existing_student.symbol_number = symbol
                        existing_student.gender = gender
                        existing_student.date_of_birth = dob_ad
                        existing_student.date_of_birth_bs = dob_bs_str
                    if student_obj:
                        # Update existing student
                        if name: student_obj.name = name
                        if symbol: student_obj.symbol_number = symbol
                        if reg_num: student_obj.registration_number = reg_num
                        if gender: student_obj.gender = gender
                        if cls: student_obj.class_obj = cls
                        if dob_ad: student_obj.date_of_birth = dob_ad
                        if dob_bs_str: student_obj.date_of_birth_bs = dob_bs_str
                        student_obj.save()
                    else:
                        # Create new student
                        Student.objects.create(
                            school=school,
                            name=name,
                            symbol_number=symbol,
                            registration_number=reg_num,
                            gender=gender,
                            class_obj=cls,
                            roll_number=get_next_roll(cls),
                            date_of_birth=dob_ad,
                            date_of_birth_bs=dob_bs_str,
                            is_active=True
                        )
                        created += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")

            if errors:
                messages.warning(request, f"Imported {created} students. However, there were some errors: {', '.join(errors[:5])}{'...' if len(errors) > 5 else ''}")
            else:
                messages.success(request, f"Successfully processed students. {created} new created, others updated.")
        except Exception as e:
            messages.error(request, f'Failed to read Excel file: {str(e)}')

        return redirect('student_list')

    return render(request, 'students/import.html', {'classes': classes})


@login_required
def student_export_excel(request):
    """Export student list to Excel."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    school = request.user.school
    active_session = school.get_active_session() if school else None
    class_id = request.GET.get('class_id')

    students = Student.objects.filter(school=school, is_active=True)
    if active_session:
        students = students.filter(class_obj__session=active_session)
    if class_id:
        students = students.filter(class_obj_id=class_id)
    students = students.select_related('class_obj')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Students'

    # Header matching import template
    headers = ['SN*', 'Symbol No', 'REG NO', 'Name of Students*', 'Gender', 'Date of Birth BS.']
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='F59E0B', end_color='F59E0B', fill_type='solid')

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    for row_num, student in enumerate(students, 2):
        ws.cell(row=row_num, column=1, value=student.roll_number or row_num - 1)
        ws.cell(row=row_num, column=2, value=student.symbol_number)
        ws.cell(row=row_num, column=3, value=student.registration_number)
        ws.cell(row=row_num, column=4, value=student.name)
        ws.cell(row=row_num, column=5, value=student.get_gender_display() or '')
        ws.cell(row=row_num, column=6, value=student.date_of_birth_bs or '')

    # Auto-width
    from openpyxl.utils import get_column_letter
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max_len + 4, 40)

    from apps.classes.models import Class
    target_class = Class.objects.filter(pk=class_id).first() if class_id else None
    filename = f"{target_class.name} Students.xlsx" if target_class else "Students.xlsx"

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def student_import_template(request):
    """Download blank Excel template for student import."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Students'
    
    headers = ['SN*', 'Symbol No', 'REG NO', 'Name of Students*', 'Gender', 'Date of Birth BS.']
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='F59E0B', end_color='F59E0B', fill_type='solid')
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    # Set column widths nicely
    from openpyxl.utils import get_column_letter
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 18)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="student_import_template.xlsx"'
    wb.save(response)
    return response
