from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from apps.teachers.models import Teacher
from apps.classes.models import Class
from apps.students.models import Student
from apps.exams.models import Exam

class TeacherDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_teacher:
            return Response({'error': 'User is not a teacher'}, status=403)
            
        try:
            teacher = request.user.teacher_profile
        except Teacher.DoesNotExist:
            return Response({'error': 'Teacher profile not found'}, status=404)
            
        active_session = request.user.school.get_active_session() if hasattr(request.user, 'school') and request.user.school else None
        
        # 1. My Classes
        my_classes_qs = Class.objects.filter(class_teacher=teacher)
        if active_session:
            my_classes_qs = my_classes_qs.filter(session=active_session)
            
        # 2. My Subjects
        assigned_class_ids = teacher.subject_assignments.values_list('subject__class_obj_id', flat=True).distinct()
        assigned_classes_qs = Class.objects.filter(id__in=assigned_class_ids)
        if active_session:
            assigned_classes_qs = assigned_classes_qs.filter(session=active_session)
            
        # Combine unique classes
        classes_qs = Class.objects.filter(
            Q(id__in=my_classes_qs.values_list('id')) | Q(id__in=assigned_classes_qs.values_list('id'))
        ).distinct()
        
        class_ids = classes_qs.values_list('id', flat=True)
        
        # KPIs
        total_classes = classes_qs.count()
        
        assignments = teacher.subject_assignments.all()
        if active_session:
            assignments = assignments.filter(subject__session=active_session)
            
        total_subjects = assignments.count()
        primary_subject = assignments.first().subject.name if assignments.exists() else "None"
        
        total_students = Student.objects.filter(class_obj__id__in=class_ids, is_active=True).count()
        
        related_exams = Exam.objects.filter(session=active_session, exam_classes__class_obj__id__in=class_ids).distinct()
        published_exams = related_exams.filter(status='PUBLISHED').count()
        total_exams = related_exams.count()
        
        return Response({
            'kpis': {
                'total_classes': total_classes,
                'total_subjects': total_subjects,
                'total_students': total_students,
                'primary_subject': primary_subject,
                'published_exams': published_exams,
                'total_exams': total_exams,
            },
            'teacher_name': f"{teacher.user.first_name} {teacher.user.last_name}".strip() or teacher.user.username
        })
