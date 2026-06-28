from rest_framework import viewsets; from rest_framework.permissions import IsAuthenticated; from .models import Exam; from core.mixins import SchoolScopedMixin
class ExamViewSet(SchoolScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Exam.objects.all()
    class serializer_class:
        pass
