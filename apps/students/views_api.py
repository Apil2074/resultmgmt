from rest_framework import viewsets; from rest_framework.permissions import IsAuthenticated; from .models import Student, StudentDeviceToken; from core.mixins import SchoolScopedMixin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

class StudentViewSet(SchoolScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Student.objects.all()
    class serializer_class:
        pass

class RegisterParentFCMTokenAPIView(APIView):
    """
    Register an FCM token for a parent tied to a specific student.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        student_id = request.data.get('student_id')

        if not token or not student_id:
            return Response({'error': 'token and student_id are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            student = Student.all_objects.get(id=student_id)
            StudentDeviceToken.objects.update_or_create(
                student=student,
                token=token
            )
            return Response({'message': 'Parent token registered successfully'})
        except Student.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
