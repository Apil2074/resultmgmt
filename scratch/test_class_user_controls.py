import os
import sys
import django

# Add backend directory to sys.path
sys.path.append(r'c:\Users\DELL\Desktop\rms\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.accounts.models import User
from apps.classes.models import Class
from apps.schools.models import AcademicSession
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
from django.test import Client
from django.urls import reverse
from django.contrib import admin
from django.test import RequestFactory
from django.contrib.messages import get_messages

print("Starting class deletion and user admin control tests...")

# Setup clients and users
client = Client()
admin_user = User.objects.get(username='admin')
school_admin = User.objects.get(username='subedi')
school = school_admin.school
session = school.get_active_session()

# Clean up leftover test classes if any
Class.objects.filter(school=school, name__in=["Test Delete 1", "Test Delete 2"]).delete()

# Create a test class to delete
test_class_1 = Class.objects.create(
    school=school,
    session=session,
    name="Test Delete 1",
    section="X"
)
test_class_2 = Class.objects.create(
    school=school,
    session=session,
    name="Test Delete 2",
    section="Y"
)

# 1. School Admin can delete a class
client.logout()
# Login as school admin
school_admin.set_password('password123')
school_admin.save()
client.post(reverse('login'), {'username': 'subedi', 'password': 'password123'})

print("Attempting to delete class as School Admin...")
response = client.post(reverse('class_list'), {
    'action': 'delete',
    'class_id': test_class_1.id
})
# Verify redirect
assert response.status_code == 302, f"Expected redirect, got {response.status_code}"
# Check if class is deleted
class_exists = Class.objects.filter(id=test_class_1.id).exists()
assert not class_exists, "Class was not deleted by School Admin!"
print("[OK] School Admin class deletion successful.")

# 2. Clean up test_class_2 using School Admin
print("Attempting to delete class 2 as School Admin...")
response = client.post(reverse('class_list'), {
    'action': 'delete',
    'class_id': test_class_2.id
})
assert response.status_code == 302
class2_exists = Class.objects.filter(id=test_class_2.id).exists()
assert not class2_exists, "Class 2 was not deleted by School Admin!"
print("[OK] School Admin class 2 deletion successful.")

# 3. Super Admin cannot edit created user account in Django admin
factory = RequestFactory()
request = factory.get('/admin/accounts/user/')
request.user = admin_user

# Get CustomUserAdmin instance
from apps.accounts.admin import CustomUserAdmin
user_admin = CustomUserAdmin(User, admin.site)

# has_change_permission(request, obj=None) should return True (so lists and general add are accessible)
assert user_admin.has_change_permission(request, None) is True, "General change permission blocked for super admin."
print("[OK] CustomUserAdmin allows general access when obj is None.")

# has_change_permission(request, obj=school_admin) should return False
assert user_admin.has_change_permission(request, school_admin) is False, "Super admin was allowed to edit an existing school admin account!"
print("[OK] CustomUserAdmin blocks edit permission on specific existing account.")

# test_class_2 was already deleted during verification tests

print("All custom security validation tests passed successfully!")
