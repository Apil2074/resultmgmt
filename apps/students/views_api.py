from rest_framework import viewsets; from rest_framework.permissions import IsAuthenticated; from .models import Student; from core.mixins import SchoolScopedMixin
class StudentViewSet(SchoolScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Student.objects.all()
    class serializer_class:
        pass
