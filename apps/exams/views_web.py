"""
Exams App — Web views with full workflow management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Exam, ExamClass


@login_required
def exam_list(request):
    school = request.user.school
    active_session = school.get_active_session() if school else None
    exams = Exam.objects.filter(school=school)
    if active_session:
        exams = exams.filter(session=active_session)
    exams = exams.select_related('session').order_by('-created_at')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            from apps.schools.models import AcademicSession
            session = get_object_or_404(AcademicSession,
                pk=request.POST.get('session_id'), school=school)
            exam = Exam.objects.create(
                school=school,
                session=session,
                name=request.POST.get('name', '').strip(),
                start_date=request.POST.get('start_date', '').strip() or None,
                end_date=request.POST.get('end_date', '').strip() or None,
                result_date=request.POST.get('result_date') or None,
                result_date_is_bs=(request.POST.get('result_date_is_bs') == 'on'),
                is_locked=(request.POST.get('is_locked') == 'on'),
                is_aggregate=(request.POST.get('is_aggregate') == 'on'),
            )
            # Link classes
            class_ids = request.POST.getlist('class_ids')
            from apps.classes.models import Class
            for cid in class_ids:
                cls = Class.objects.filter(pk=cid, school=school).first()
                if cls:
                    ExamClass.objects.create(exam=exam, class_obj=cls)
            messages.success(request, f'Exam "{exam.name}" created.')
        return redirect('exam_list')

    from apps.schools.models import AcademicSession
    from apps.classes.models import Class
    sessions = AcademicSession.objects.filter(school=school)
    classes = Class.objects.filter(school=school).order_by('numeric_level', 'name', 'section')
    if active_session:
        classes = classes.filter(session=active_session)
    return render(request, 'exams/list.html', {
        'exams': exams,
        'sessions': sessions,
        'classes': classes,
    })


@login_required
def exam_detail(request, pk):
    school = request.user.school
    exam = get_object_or_404(Exam, pk=pk, school=school)
    exam_classes = exam.exam_classes.select_related('class_obj')

    if request.method == 'POST':
        if request.user.role not in [request.user.Role.SUPER_ADMIN, request.user.Role.SCHOOL_ADMIN]:
            messages.error(request, 'Access denied.')
            return redirect('exam_detail', pk=pk)
            
        action = request.POST.get('action')
        
        if action == 'add_classes':
            if not exam.is_editable:
                messages.error(request, 'Cannot modify classes for this exam as it is locked or not in DRAFT state.')
                return redirect('exam_detail', pk=pk)
                
            class_ids = request.POST.getlist('class_ids')
            from apps.classes.models import Class
            added_count = 0
            for cid in class_ids:
                cls = Class.objects.filter(pk=cid, school=school, session=exam.session).first()
                if cls:
                    ExamClass.objects.get_or_create(exam=exam, class_obj=cls)
                    added_count += 1
            
            if added_count > 0:
                messages.success(request, f'Successfully added {added_count} class(es) to the exam.')
            else:
                messages.warning(request, 'No classes were added.')
            return redirect('exam_detail', pk=pk)

        elif action == 'remove_class':
            if not exam.is_editable:
                messages.error(request, 'Cannot modify classes for this exam as it is locked or not in DRAFT state.')
                return redirect('exam_detail', pk=pk)
                
            class_id = request.POST.get('class_id')
            exam_class = exam.exam_classes.filter(class_obj_id=class_id).first()
            if exam_class:
                class_name = exam_class.class_obj.full_name
                exam_class.delete()
                messages.success(request, f'Removed class "{class_name}" from the exam.')
            else:
                messages.error(request, 'Class not found in this exam.')
            return redirect('exam_detail', pk=pk)

    # Find classes already added
    added_class_ids = exam_classes.values_list('class_obj_id', flat=True)
    from apps.classes.models import Class
    available_classes = Class.objects.filter(
        school=school, 
        session=exam.session
    ).exclude(id__in=added_class_ids)

    return render(request, 'exams/detail.html', {
        'exam': exam,
        'exam_classes': exam_classes,
        'available_classes': available_classes,
        'aggregation_rules': exam.aggregation_rules.all() if exam.is_aggregate else [],
    })


@login_required
def exam_workflow(request, pk):
    """Handle exam status transitions."""
    school = request.user.school
    exam = get_object_or_404(Exam, pk=pk, school=school)
    action = request.POST.get('action')
    user = request.user

    workflow_map = {
        'publish': (Exam.Status.DRAFT, Exam.Status.PUBLISHED, 'Results published successfully!'),
        'unpublish': (None, None, 'Exam unpublished and editable.'),
    }

    if action in workflow_map:
        from_status, to_status, msg = workflow_map[action]
        if action == 'unpublish':
            if user.can_manage_school():
                exam.unpublish()
                messages.success(request, msg)
            else:
                messages.error(request, 'Permission denied.')
        elif action == 'publish':
            if user.can_publish_results():
                exam.publish(user)
                messages.success(request, msg)
            else:
                messages.error(request, 'Permission denied.')
        elif exam.status == from_status and user.can_publish_results():
            exam.status = to_status
            exam.save()
            messages.success(request, msg)
        else:
            messages.error(request, 'Cannot perform this action.')

    return redirect('exam_detail', pk=pk)

@login_required
def exam_edit(request, pk):
    school = request.user.school
    exam = get_object_or_404(Exam, pk=pk, school=school)
    
    if not exam.is_editable:
        messages.error(request, 'Cannot edit this exam as it is locked or not in DRAFT state.')
        return redirect('exam_detail', pk=pk)

    if request.method == 'POST':
        exam.name = request.POST.get('name', '').strip()
        exam.start_date = request.POST.get('start_date', '').strip() or None
        exam.end_date = request.POST.get('end_date', '').strip() or None
        exam.result_date = request.POST.get('result_date') or None
        exam.result_date_is_bs = (request.POST.get('result_date_is_bs') == 'on')
        exam.is_locked = (request.POST.get('is_locked') == 'on')
        exam.is_aggregate = (request.POST.get('is_aggregate') == 'on')
        
        session_id = request.POST.get('session_id')
        if session_id:
            from apps.schools.models import AcademicSession
            session = get_object_or_404(AcademicSession, pk=session_id, school=school)
            exam.session = session
            
        exam.save()
        
        # update exam classes
        class_ids = request.POST.getlist('class_ids')
        from apps.classes.models import Class
        
        current_class_ids = set(exam.exam_classes.values_list('class_obj_id', flat=True))
        new_class_ids = set(int(cid) for cid in class_ids)
        
        classes_to_remove = current_class_ids - new_class_ids
        classes_to_add = new_class_ids - current_class_ids
        
        if classes_to_remove:
            exam.exam_classes.filter(class_obj_id__in=classes_to_remove).delete()
            
        for cid in classes_to_add:
            cls = Class.objects.filter(pk=cid, school=school).first()
            if cls:
                ExamClass.objects.create(exam=exam, class_obj=cls)
                
        messages.success(request, f'Exam "{exam.name}" updated.')
        return redirect('exam_detail', pk=pk)
        
    from apps.schools.models import AcademicSession
    from apps.classes.models import Class
    sessions = AcademicSession.objects.filter(school=school)
    classes = Class.objects.filter(school=school, session=exam.session).order_by('numeric_level', 'name', 'section')
    current_class_ids = list(exam.exam_classes.values_list('class_obj_id', flat=True))
    
    return render(request, 'exams/edit.html', {
        'exam': exam,
        'sessions': sessions,
        'classes': classes,
        'current_class_ids': current_class_ids,
    })


@login_required
def exam_delete(request, pk):
    school = request.user.school
    exam = get_object_or_404(Exam, pk=pk, school=school)
    
    if not exam.is_editable and not request.user.can_manage_school():
        messages.error(request, 'Cannot delete this exam as it is locked or not in DRAFT state.')
        return redirect('exam_detail', pk=pk)

    if request.method == 'POST':
        exam_name = exam.name
        exam.delete()
        messages.success(request, f'Exam "{exam_name}" deleted successfully.')
        return redirect('exam_list')
        
    return render(request, 'exams/delete.html', {
        'exam': exam
    })


@login_required
def exam_aggregation_rules(request, pk):
    school = request.user.school
    exam = get_object_or_404(Exam, pk=pk, school=school, is_aggregate=True)

    if not exam.is_editable:
        messages.error(request, 'Cannot edit this exam as it is locked.')
        return redirect('exam_detail', pk=pk)

    from .models import ExamAggregationRule

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_rule':
            source_exam_id = request.POST.get('source_exam_id')
            weight = request.POST.get('weight_percentage')
            try:
                source_exam = Exam.objects.get(pk=source_exam_id, school=school)
                ExamAggregationRule.objects.create(
                    aggregate_exam=exam,
                    source_exam=source_exam,
                    weight_percentage=weight
                )
                messages.success(request, f'Added {source_exam.name} with weight {weight}%')
            except Exception as e:
                messages.error(request, f'Error adding rule: {e}')
        
        elif action == 'delete_rule':
            rule_id = request.POST.get('rule_id')
            rule = ExamAggregationRule.objects.filter(pk=rule_id, aggregate_exam=exam).first()
            if rule:
                rule.delete()
                messages.success(request, 'Rule deleted.')
                
        return redirect('exam_aggregation_rules', pk=pk)

    rules = exam.aggregation_rules.select_related('source_exam')
    available_exams = Exam.objects.filter(
        school=school, 
        session=exam.session
    ).exclude(id=exam.id).exclude(id__in=rules.values_list('source_exam_id', flat=True))

    return render(request, 'exams/aggregate_rules.html', {
        'exam': exam,
        'rules': rules,
        'available_exams': available_exams,
    })


@login_required
def exam_generate_aggregate(request, pk):
    school = request.user.school
    exam = get_object_or_404(Exam, pk=pk, school=school, is_aggregate=True)

    if not request.user.can_manage_school():
        messages.error(request, 'Permission denied.')
        return redirect('exam_detail', pk=pk)

    if request.method == 'POST':
        from .services import ExamAggregationService
        try:
            service = ExamAggregationService(exam)
            count = service.generate_aggregate_marks()
            messages.success(request, f'Successfully generated aggregate marks for {count} subjects/students.')
        except Exception as e:
            messages.error(request, f'Error generating aggregate results: {e}')

    return redirect('exam_detail', pk=pk)

