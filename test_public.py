import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms.settings')
try:
    django.setup()
except Exception as e:
    print("Could not setup with rms.settings, trying backend.settings")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()

from django.test import Client
from apps.students.models import Student
from apps.exams.models import Exam
from apps.results.models import StudentResult
import traceback

print("--- Testing Public Report Card Endpoint ---")
try:
    s = Student.objects.filter(registration_number__isnull=False).exclude(registration_number='').first()
    if not s:
        print("No student with registration number found.")
        s = Student.objects.first()
    
    e = Exam.objects.filter(status='PUBLISHED').first()
    if not e:
        print("No PUBLISHED exam found.")
    
    if s and e:
        print(f"Student: {s.name} (ID: {s.id})")
        print(f"Exam: {e.name} (ID: {e.id})")
        
        # Ensure a StudentResult exists
        sr, created = StudentResult.objects.get_or_create(exam=e, student=s, school=s.school)
        if created:
            print("Created a dummy StudentResult to test.")
        
        c = Client()
        session = c.session
        session['auth_student_id'] = s.id
        session.save()
        
        url = f'/results/public/report/{e.id}/{s.id}/'
        print(f"Fetching URL: {url}")
        resp = c.get(url)
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 302:
            print(f"Redirect URL: {resp.url}")
        elif resp.status_code == 500:
            print("HTTP 500 Server Error! HTML snippet:")
            print(resp.content.decode('utf-8')[:2000])
        elif resp.status_code == 200:
            print("HTTP 200 OK! HTML length:", len(resp.content))
            html = resp.content.decode('utf-8')
            if 'THE GRADE(S) SECURED BY' in html:
                print("Marksheet rendered successfully!")
            else:
                print("Marksheet might not have rendered correctly. HTML snippet:")
                print(html[:1000])
except Exception as e:
    print("Exception occurred!")
    traceback.print_exc()

print("Done.")
