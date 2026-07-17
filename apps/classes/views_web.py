"""
Classes App — Web views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models.functions import Length
from .models import Class


@login_required
def class_list(request):
    school = request.user.school
    active_session = school.get_active_session() if school else None
    classes_qs = Class.objects.filter(school=school)
    if active_session:
        classes_qs = classes_qs.filter(session=active_session)
    classes_qs = classes_qs.select_related(
        'session', 'class_teacher'
    )
    
    classes = list(classes_qs)

    if request.method == 'POST':
        if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
            messages.error(request, 'Access denied.')
            return redirect('class_list')
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            section = request.POST.get('section', '').strip()
            numeric_level = request.POST.get('numeric_level', '0').strip()
            if not numeric_level.isdigit():
                numeric_level = 0
            session_id = request.POST.get('session_id')
            teacher_id = request.POST.get('teacher_id')
            teacher_name = request.POST.get('teacher_name', '').strip()
            teacher_phone = request.POST.get('teacher_phone', '').strip()
            teacher_email = request.POST.get('teacher_email', '').strip()

            from apps.schools.models import AcademicSession
            session = get_object_or_404(AcademicSession, pk=session_id, school=school)

            cls = Class.objects.create(
                school=school, session=session, name=name, section=section, numeric_level=numeric_level
            )
            
            if teacher_id:
                from apps.teachers.models import Teacher
                teacher_obj = Teacher.objects.filter(id=teacher_id, school=school).first()
                if teacher_obj:
                    cls.class_teacher = teacher_obj
                    cls.save()
            messages.success(request, f'Class "{cls.full_name}" created.')

        elif action == 'delete':
            cls_id = request.POST.get('class_id')
            cls = get_object_or_404(Class, pk=cls_id, school=school)
            cls_name = cls.full_name
            cls.delete()
            messages.success(request, f'Class "{cls_name}" and all its students deleted.')
 
        elif action == 'edit_class':
            cls_id = request.POST.get('class_id')
            cls = get_object_or_404(Class, pk=cls_id, school=school)
            new_name = request.POST.get('name', '').strip()
            new_section = request.POST.get('section', '').strip()
            new_numeric_level = request.POST.get('numeric_level', str(cls.numeric_level)).strip()
            if not new_numeric_level.isdigit():
                new_numeric_level = 0
            teacher_id = request.POST.get('teacher_id')

            if new_name:
                cls.name = new_name
                cls.section = new_section
                cls.numeric_level = new_numeric_level
                # Regenerate slug if name/section changed
                from django.utils.text import slugify
                cls.slug = slugify(f"{cls.full_name}-{cls.session.name}")
                if teacher_id:
                    from apps.teachers.models import Teacher
                    teacher_obj = Teacher.objects.filter(id=teacher_id, school=school).first()
                    cls.class_teacher = teacher_obj
                else:
                    cls.class_teacher = None
                cls.save()

            messages.success(request, f'Class "{cls.full_name}" updated successfully.')

        elif action == 'reorder_classes':
            from django.http import JsonResponse
            try:
                class_ids = request.POST.getlist('class_ids')
                for index, c_id in enumerate(class_ids):
                    # using numeric_level = index + 1 ensures it starts from 1
                    Class.objects.filter(pk=c_id, school=school).update(numeric_level=index + 1)
                return JsonResponse({'status': 'success'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

        return redirect('class_list')

    from apps.schools.models import AcademicSession
    from apps.teachers.models import Teacher
    sessions = AcademicSession.objects.filter(school=school)
    teachers = Teacher.objects.filter(school=school, is_active=True).order_by('name')
    return render(request, 'classes/list.html', {
        'classes': classes,
        'sessions': sessions,
        'active_session': active_session,
        'teachers': teachers,
    })


@login_required
def class_detail(request, slug):
    school = request.user.school
    cls = get_object_or_404(Class, slug=slug, school=school)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action != 'map_subjects' and request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
            messages.error(request, 'Access denied.')
            return redirect('class_detail', slug=cls.slug)
        if action == 'add_student':
            from apps.students.models import Student
            name = request.POST.get('name', '').strip()
            roll_number = request.POST.get('roll_number', '').strip()
            gender = request.POST.get('gender', 'M')
            symbol_number = request.POST.get('symbol_number', '').strip()
            registration_number = request.POST.get('registration_number', '').strip()

            if name and roll_number:
                if Student.objects.filter(school=school, class_obj=cls, roll_number=roll_number).exists():
                    messages.error(request, f'A student with Roll Number "{roll_number}" already exists in this class.')
                elif registration_number and Student.objects.filter(school=school, registration_number=registration_number).exists():
                    messages.error(request, f'A student with Registration Number "{registration_number}" already exists.')
                elif symbol_number and Student.objects.filter(school=school, symbol_number=symbol_number).exists():
                    messages.error(request, f'A student with Symbol Number "{symbol_number}" already exists.')
                else:
                    Student.objects.create(
                        school=school,
                        class_obj=cls,
                        name=name,
                        roll_number=roll_number,
                        gender=gender,
                        symbol_number=symbol_number,
                        registration_number=registration_number,
                        is_active=True
                    )
                    messages.success(request, f'Student "{name}" added to this class.')
            else:
                messages.error(request, 'Student name and roll number are required.')

        elif action == 'map_subjects':
            from apps.students.models import Student
            from apps.subjects.models import StudentSubjectEnrollment, Subject
            student_id = request.POST.get('student_id')
            student = get_object_or_404(Student, pk=student_id, class_obj=cls, school=school)
            checked_subject_ids = request.POST.getlist('subject_ids')

            optional_subjects = cls.subjects.filter(subject_type=Subject.SubjectType.OPTIONAL)
            optional_subject_ids = [str(s.id) for s in optional_subjects]

            # Clear existing optional enrollments for this student in this class
            StudentSubjectEnrollment.objects.filter(
                student=student,
                subject__class_obj=cls
            ).delete()

            # Create new enrollments
            for sub_id in checked_subject_ids:
                if sub_id in optional_subject_ids:
                    StudentSubjectEnrollment.objects.create(
                        student=student,
                        subject_id=sub_id
                    )
            messages.success(request, f'Subjects mapped successfully for {student.name}.')

        elif action == 'add_subjects':
            from apps.subjects.models import Subject
            codes = request.POST.getlist('code')
            names = request.POST.getlist('name')
            theory_credits = request.POST.getlist('theory_credit_hour')
            orders = request.POST.getlist('order')
            subject_types = request.POST.getlist('subject_type')
            has_practicals = request.POST.getlist('has_practical')
            practical_codes = request.POST.getlist('practical_code')
            practical_credits = request.POST.getlist('practical_credit_hour')

            count = len(codes)
            created_count = 0

            for i in range(count):
                code = codes[i].strip()
                name = names[i].strip()
                if not code or not name:
                    continue

                try:
                    t_credit = float(theory_credits[i]) if (i < len(theory_credits) and theory_credits[i]) else 3.0
                except ValueError:
                    messages.error(request, f"Invalid theory credit hour value: {theory_credits[i] if i < len(theory_credits) else ''}")
                    continue

                try:
                    ord_val = int(orders[i]) if (i < len(orders) and orders[i]) else 0
                except ValueError:
                    messages.error(request, f"Invalid display order value: {orders[i] if i < len(orders) else ''}")
                    continue

                sub_type = subject_types[i] if i < len(subject_types) else 'COMPULSORY'
                has_prac = (has_practicals[i] == 'yes') if i < len(has_practicals) else False
                p_code = practical_codes[i].strip() if (has_prac and i < len(practical_codes)) else ''
                
                try:
                    p_credit = float(practical_credits[i]) if (has_prac and i < len(practical_credits) and practical_credits[i]) else 0.0
                except ValueError:
                    messages.error(request, f"Invalid practical credit hour value: {practical_credits[i] if i < len(practical_credits) else ''}")
                    continue

                Subject.objects.create(
                    school=school,
                    class_obj=cls,
                    code=code,
                    name=name,
                    theory_credit_hour=t_credit,
                    has_practical=has_prac,
                    practical_code=p_code,
                    practical_credit_hour=p_credit,
                    subject_type=sub_type,
                    order=ord_val
                )
                created_count += 1

            if created_count > 0:
                messages.success(request, f'{created_count} subjects added to this class.')
            else:
                messages.error(request, 'No valid subjects were entered.')

        elif action == 'edit_subject':
            from apps.subjects.models import Subject
            subj_id = request.POST.get('subject_id')
            subj = get_object_or_404(Subject, pk=subj_id, class_obj=cls, school=school)
            
            code = request.POST.get('code', '').strip()
            name = request.POST.get('name', '').strip()
            
            try:
                t_credit = float(request.POST.get('theory_credit_hour') or 3.0)
            except ValueError:
                messages.error(request, "Invalid theory credit hour format.")
                return redirect('class_detail', slug=cls.slug)

            try:
                ord_val = int(request.POST.get('order') or 0)
            except ValueError:
                messages.error(request, "Invalid display order format.")
                return redirect('class_detail', slug=cls.slug)

            sub_type = request.POST.get('subject_type', 'COMPULSORY')
            has_prac = request.POST.get('has_practical') == 'yes'
            p_code = request.POST.get('practical_code', '').strip() if has_prac else ''
            
            try:
                p_credit = float(request.POST.get('practical_credit_hour') or 0.0) if has_prac else 0.0
            except ValueError:
                messages.error(request, "Invalid practical credit hour format.")
                return redirect('class_detail', slug=cls.slug)

            subj.code = code
            subj.name = name
            subj.theory_credit_hour = t_credit
            subj.order = ord_val
            subj.subject_type = sub_type
            subj.has_practical = has_prac
            subj.practical_code = p_code
            subj.practical_credit_hour = p_credit
            subj.save()

            messages.success(request, f'Subject "{name}" updated.')

        elif action == 'delete_subject':
            from apps.subjects.models import Subject
            subj_id = request.POST.get('subject_id')
            subj = get_object_or_404(Subject, pk=subj_id, class_obj=cls, school=school)
            subj_name = subj.name
            subj.delete()
            messages.success(request, f'Subject "{subj_name}" deleted.')

        elif action == 'reorder_subjects':
            from django.http import JsonResponse
            from apps.subjects.models import Subject
            try:
                subject_ids = request.POST.getlist('subject_ids')
                for index, sub_id in enumerate(subject_ids):
                    Subject.objects.filter(pk=sub_id, class_obj=cls, school=school).update(order=index)
                return JsonResponse({'status': 'success'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

        return redirect('class_detail', slug=cls.slug)

    students = cls.students.filter(is_active=True)
    subjects = cls.subjects.all().select_related().order_by('order', 'name')

    from apps.subjects.models import Subject
    optional_subjects = cls.subjects.filter(subject_type=Subject.SubjectType.OPTIONAL).order_by('order', 'name')

    for student in students:
        student.enrolled_subject_ids = list(
            student.subject_enrollments.filter(
                subject__class_obj=cls
            ).values_list('subject_id', flat=True)
        )

    return render(request, 'classes/detail.html', {
        'class_obj': cls,
        'students': students,
        'subjects': subjects,
        'optional_subjects': optional_subjects,
    })


@login_required
def bulk_map_subjects(request, slug):
    school = request.user.school
    cls = get_object_or_404(Class, slug=slug, school=school)

    from apps.subjects.models import Subject, StudentSubjectEnrollment
    from apps.students.models import Student
    from django.db import transaction

    optional_subjects = cls.subjects.filter(subject_type=Subject.SubjectType.OPTIONAL).order_by('order', 'name')
    students = cls.students.filter(is_active=True).order_by(Length('roll_number'), 'roll_number', 'name')

    if request.method == 'POST':
        with transaction.atomic():
            # Delete existing optional subject enrollments for these students and optional subjects
            StudentSubjectEnrollment.objects.filter(
                student__in=students,
                subject__in=optional_subjects
            ).delete()

            enrollments_to_create = []
            for student in students:
                checked_subject_ids = request.POST.getlist(f'student_subjects_{student.id}')
                for sub_id in checked_subject_ids:
                    try:
                        sub_id_int = int(sub_id)
                    except ValueError:
                        continue

                    if sub_id_int in [s.id for s in optional_subjects]:
                        enrollments_to_create.append(
                            StudentSubjectEnrollment(
                                student=student,
                                subject_id=sub_id_int
                            )
                        )

            if enrollments_to_create:
                StudentSubjectEnrollment.objects.bulk_create(enrollments_to_create)

            messages.success(request, f"Bulk optional subjects mapping updated for class {cls.full_name}.")
            return redirect('class_detail', slug=cls.slug)

    # Fetch existing mappings
    enrolled_pairs = set(
        StudentSubjectEnrollment.objects.filter(
            student__in=students,
            subject__in=optional_subjects
        ).values_list('student_id', 'subject_id')
    )

    student_data = []
    for s in students:
        s_enrolled_ids = [sub_id for student_id, sub_id in enrolled_pairs if student_id == s.id]
        student_data.append({
            'student': s,
            'enrolled_ids': s_enrolled_ids
        })

    return render(request, 'classes/bulk_map_subjects.html', {
        'class_obj': cls,
        'optional_subjects': optional_subjects,
        'student_data': student_data,
    })


@login_required
def class_spreadsheet_edit(request, slug):
    school = request.user.school
    cls = get_object_or_404(Class, slug=slug, school=school)
    
    if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('class_detail', slug=cls.slug)

    # Get all active students for this class ordered by roll number
    from django.db.models.functions import Length
    students = cls.students.filter(is_active=True).order_by(Length('roll_number'), 'roll_number', 'name')
    
    return render(request, 'classes/spreadsheet_edit.html', {
        'class_obj': cls,
        'students': students,
    })
