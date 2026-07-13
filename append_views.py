import os
path = r"c:\Users\wwwap\Desktop\resultmgmt\apps\schools\views_web.py"

views_code = """
# -----------------------------------------------------------------------------
# SUPPORT TICKETS
# -----------------------------------------------------------------------------

@login_required
def support_ticket_list(request):
    \"\"\"School Admin view to list their tickets and create new ones.\"\"\"
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
    \"\"\"School Admin view to see a ticket thread and reply.\"\"\"
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
    \"\"\"Super Admin view to list all tickets.\"\"\"
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
    \"\"\"Super Admin view to read and reply to a specific ticket.\"\"\"
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
"""

with open(path, "a", encoding="utf-8") as f:
    f.write(views_code)

