"""
Subjects App — Web views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from .models import Subject, SubjectMarkingStructure


@login_required
def subject_list(request):
    school = request.user.school
    active_session = school.get_active_session() if school else None
    class_id = request.GET.get('class_id', '')
    from apps.classes.models import Class
    classes = Class.objects.filter(school=school)
    subjects = Subject.objects.filter(school=school)
    
    if active_session:
        classes = classes.filter(session=active_session)
        subjects = subjects.filter(class_obj__session=active_session)
        
    subjects = subjects.select_related('class_obj', 'marking_structure')
    if class_id:
        subjects = subjects.filter(class_obj_id=class_id)

    if request.method == 'POST':
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
            
            created_count = 0
            subject_count = len(codes)

            for cid in class_ids:
                cls = get_object_or_404(Class, pk=cid, school=school)
                for i in range(subject_count):
                    code = codes[i].strip()
                    name = names[i].strip()
                    if not code or not name:
                        continue
                        
                    theory_credit_hour = float(theory_credits[i]) if i < len(theory_credits) else 3.0
                    subject_type = subject_types[i] if i < len(subject_types) else 'COMPULSORY'
                    order = int(orders[i]) if i < len(orders) else 0
                    
                    has_practical = (has_practicals[i] == 'yes') if i < len(has_practicals) else False
                    practical_code = practical_codes[i].strip() if (has_practical and i < len(practical_codes)) else ''
                    practical_ch = float(practical_credits[i]) if (has_practical and i < len(practical_credits) and practical_credits[i]) else 0.0

                    try:
                        Subject.objects.create(
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
                    except IntegrityError:
                        messages.error(request, f"Subject with code '{code}' already exists for class '{cls.name}'.")
                        continue
                created_count += 1
            messages.success(request, f'{subject_count} subject(s) created across {created_count} class(es).')
        elif action == 'delete':
            subj = get_object_or_404(Subject, pk=request.POST.get('subject_id'), school=school)
            subj.delete()
            messages.success(request, 'Subject deleted.')
        return redirect('subject_list')

    return render(request, 'subjects/list.html', {
        'subjects': subjects,
        'classes': classes,
        'class_id': class_id,
    })
