"""Backup App — Web views"""
import os
import subprocess
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.conf import settings


@login_required
def backup_index(request):
    if not request.user.can_manage_school():
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')
    backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    backups = []
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.sql'):
                path = os.path.join(backup_dir, f)
                backups.append({'name': f, 'size': os.path.getsize(path), 'path': path})
    return render(request, 'backup/index.html', {'backups': backups[:20]})


@login_required
def create_backup(request):
    if not request.user.can_manage_school():
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')
    if request.method == 'POST':
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'rms_backup_{timestamp}.sql'
        filepath = os.path.join(backup_dir, filename)
        db = settings.DATABASES['default']
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = db.get('PASSWORD', '')
            result = subprocess.run([
                'pg_dump',
                '-h', db.get('HOST', 'localhost'),
                '-p', str(db.get('PORT', 5432)),
                '-U', db.get('USER', ''),
                '-d', db.get('NAME', ''),
                '-f', filepath,
            ], env=env, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                messages.success(request, f'Backup created: {filename}')
            else:
                messages.error(request, f'Backup failed: {result.stderr[:200]}')
        except Exception as e:
            messages.error(request, f'Backup error: {str(e)}')
    return redirect('backup_index')


@login_required
def restore_backup(request):
    if not request.user.is_super_admin:
        messages.error(request, 'Only Super Admin can restore backups.')
        return redirect('backup_index')
    messages.warning(request, 'Restore functionality requires manual intervention for safety.')
    return redirect('backup_index')
