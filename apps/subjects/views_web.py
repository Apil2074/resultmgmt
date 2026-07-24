"""
Subjects App — Web views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from .models import Subject


@login_required
def subject_list(request):
    school = request.user.school
    active_session = school.get_active_session() if school else None
    class_id = request.GET.get('class_id', '')
    from apps.classes.models import Class
    classes = Class.objects.filter(school=school)
    
    if active_session:
        classes = classes.filter(session=active_session)
        
    if class_id:
        classes = classes.filter(id=class_id)
        
    classes = classes.prefetch_related('subjects')

    if request.method == 'POST':
        if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
            messages.error(request, 'Access denied.')
            return redirect('subject_list')
        action = request.POST.get('action')
        if action == 'create':
            class_ids = request.POST.getlist('class_ids')
            if not class_ids:
                messages.error(request, 'Please select at least one class.')
                return redirect('subject_list')
                
            codes = request.POST.getlist('code[]')
            names = request.POST.getlist('name[]')
            theory_credits = request.POST.getlist('theory_credit_hour[]')
            subject_types = request.POST.getlist('subject_type[]')
            has_practicals = request.POST.getlist('has_practical[]')
            practical_codes = request.POST.getlist('practical_code[]')
            practical_credits = request.POST.getlist('practical_credit_hour[]')
            orders = request.POST.getlist('order[]')
            
            from django.db import transaction

            subject_count = len(codes)
            subjects_to_create = []
            has_error = False
            seen_codes = set()

            for cid in class_ids:
                cls = get_object_or_404(Class, pk=cid, school=school)
                for i in range(subject_count):
                    code = codes[i].strip()
                    name = names[i].strip()
                    if not code or not name:
                        continue
                        
                    try:
                        theory_credit_hour = float(theory_credits[i]) if (i < len(theory_credits) and theory_credits[i]) else 3.0
                    except ValueError:
                        messages.error(request, f"Invalid theory credit hour value for {name}.")
                        has_error = True
                        break

                    subject_type = subject_types[i] if i < len(subject_types) else 'COMPULSORY'
                    
                    try:
                        order = int(orders[i]) if (i < len(orders) and orders[i]) else 0
                    except ValueError:
                        messages.error(request, f"Invalid display order value for {name}.")
                        has_error = True
                        break
                    
                    has_practical = (has_practicals[i] == 'yes') if i < len(has_practicals) else False
                    practical_code = practical_codes[i].strip() if (has_practical and i < len(practical_codes)) else ''
                    
                    try:
                        practical_ch = float(practical_credits[i]) if (has_practical and i < len(practical_credits) and practical_credits[i]) else 0.0
                    except ValueError:
                        messages.error(request, f"Invalid practical credit hour value for {name}.")
                        has_error = True
                        break

                    if (cid, code) in seen_codes:
                        messages.error(request, f"Duplicate subject code '{code}' in your submission for class '{cls.name}'.")
                        has_error = True
                        break
                        
                    if Subject.objects.filter(class_obj=cls, code=code, school=school).exists():
                        messages.error(request, f"Subject with code '{code}' already exists for class '{cls.name}'.")
                        has_error = True
                        break
                        
                    seen_codes.add((cid, code))
                        
                    sub = Subject(
                        school=school,
                        class_obj=cls,
                        code=code,
                        name=name,
                        theory_credit_hour=theory_credit_hour,
                        has_practical=has_practical,
                        practical_credit_hour=practical_ch,
                        practical_code=practical_code,
                        subject_type=subject_type,
                        order=order,
                    )
                    
                    try:
                        sub.clean()
                    except ValidationError as ve:
                        messages.error(request, f"Validation error for '{name}': {ve.message if hasattr(ve, 'message') else ve}")
                        has_error = True
                        break
                        
                    subjects_to_create.append(sub)
                    
                if has_error:
                    break

            if has_error:
                messages.error(request, 'No subjects were created due to errors. Please correct them and try again.')
            elif subjects_to_create:
                try:
                    with transaction.atomic():
                        Subject.objects.bulk_create(subjects_to_create)
                        
                    unique_classes = len(set([sub.class_obj_id for sub in subjects_to_create]))
                    messages.success(request, f'{len(subjects_to_create)} subject(s) created successfully across {unique_classes} class(es).')
                except Exception as e:
                    messages.error(request, f"An unexpected error occurred during creation: {str(e)}")
        elif action == 'delete':
            subj = get_object_or_404(Subject, pk=request.POST.get('subject_id'), school=school)
            subj.delete()
            messages.success(request, 'Subject deleted.')
        elif action == 'edit':
            subj = get_object_or_404(Subject, pk=request.POST.get('subject_id'), school=school)
            subj.name = request.POST.get('name', subj.name).strip()
            subj.code = request.POST.get('code', subj.code).strip()
            
            try:
                subj.theory_credit_hour = float(request.POST.get('theory_credit_hour', subj.theory_credit_hour))
            except ValueError:
                messages.error(request, 'Invalid theory credit hour format.')
                
            subj.subject_type = request.POST.get('subject_type', subj.subject_type)
            
            subj.has_practical = request.POST.get('has_practical') == 'yes'
            if subj.has_practical:
                subj.practical_code = request.POST.get('practical_code', '').strip()
                try:
                    subj.practical_credit_hour = float(request.POST.get('practical_credit_hour', 0.0))
                except ValueError:
                    messages.error(request, 'Invalid practical credit hour format.')
            else:
                subj.practical_code = ''
                subj.practical_credit_hour = 0.0
                
            try:
                subj.save()
                messages.success(request, f'Subject "{subj.name}" updated successfully.')
            except ValidationError as ve:
                messages.error(request, f"Validation error: {ve.message if hasattr(ve, 'message') else ve}")
            except IntegrityError:
                messages.error(request, f'Subject with code "{subj.code}" already exists for this class.')
        elif action == 'reorder_subjects':
            from django.http import JsonResponse
            try:
                subject_ids = request.POST.getlist('subject_ids[]')
                for index, sub_id in enumerate(subject_ids):
                    Subject.objects.filter(pk=sub_id, school=school).update(order=index)
                return JsonResponse({'status': 'success'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        elif action == 'clone_subject':
            from django.http import JsonResponse
            try:
                source_subject = get_object_or_404(Subject, pk=request.POST.get('subject_id'), school=school)
                target_class_id = request.POST.get('target_class_id')
                target_class = get_object_or_404(Class, pk=target_class_id, school=school)
                
                # Clone subject properties
                new_subject = Subject(
                    school=school,
                    class_obj=target_class,
                    session=target_class.session,
                    code=source_subject.code,
                    name=source_subject.name,
                    theory_credit_hour=source_subject.theory_credit_hour,
                    has_practical=source_subject.has_practical,
                    practical_credit_hour=source_subject.practical_credit_hour,
                    practical_code=source_subject.practical_code,
                    subject_type=source_subject.subject_type,
                    order=999 # temporary order, will be updated by subsequent reorder AJAX
                )
                new_subject.save()
                
                from django.template.loader import render_to_string
                html = render_to_string('subjects/partials/subject_item.html', {'sub': new_subject, 'user': request.user}, request=request)
                
                return JsonResponse({'status': 'success', 'new_subject_id': new_subject.id, 'html': html})
            except IntegrityError:
                return JsonResponse({'status': 'error', 'message': f'A subject with code "{source_subject.code}" already exists in this class.'}, status=400)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        return redirect('subject_list')

    all_classes = Class.objects.filter(school=school)
    if active_session:
        all_classes = all_classes.filter(session=active_session)

    from apps.schools.models import SystemSetting
    system_settings = SystemSetting.get_settings()
    
    return render(request, 'subjects/list.html', {
        'classes': classes,
        'all_classes': all_classes,
        'class_id': class_id,
        'system_settings': system_settings,
    })
@login_required
def subject_spreadsheet_edit(request):
    school = request.user.school
    active_session = school.get_active_session() if school else None
    class_id = request.GET.get('class_id', '')
    
    from apps.classes.models import Class
    subjects = Subject.objects.filter(school=school)
    
    if active_session:
        subjects = subjects.filter(class_obj__session=active_session)
        
    if class_id:
        subjects = subjects.filter(class_obj_id=class_id)
        class_obj = get_object_or_404(Class, id=class_id, school=school)
    else:
        class_obj = None

    subjects = subjects.select_related('class_obj').order_by('class_obj__numeric_level', 'class_obj__name', 'order', 'name')
    
    if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
        messages.error(request, 'Access denied.')
        return redirect('subject_list')

    return render(request, 'subjects/spreadsheet_edit.html', {
        'subjects': subjects,
        'class_obj': class_obj,
        'class_id': class_id,
    })

@login_required
def subject_inline_edit(request, subject_id):
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    
    school = request.user.school
    subject = get_object_or_404(Subject, pk=subject_id, school=school)
    
    if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
        return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)
        
    field_name = request.POST.get('name')
    value = request.POST.get('value')
    
    allowed_fields = [
        'code', 'name', 'theory_credit_hour', 'has_practical', 'practical_code', 
        'practical_credit_hour', 'subject_type', 'order',
        'theory_full_marks', 'theory_pass_marks', 'practical_full_marks', 'practical_pass_marks'
    ]
    if field_name not in allowed_fields:
        return JsonResponse({'status': 'error', 'message': 'Invalid field'}, status=400)
        
    try:
        if field_name == 'has_practical':
            value = value == 'True'
        elif field_name in ['theory_credit_hour', 'practical_credit_hour', 'theory_full_marks', 'theory_pass_marks', 'practical_full_marks', 'practical_pass_marks']:
            value = float(value) if value else 0.0
        elif field_name == 'order':
            value = int(value) if value else 0
            
        setattr(subject, field_name, value)
        subject.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
