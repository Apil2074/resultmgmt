from rest_framework import viewsets; from rest_framework.permissions import IsAuthenticated; from .models import Class; from core.mixins import SchoolScopedMixin
class ClassViewSet(SchoolScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Class.objects.all()
    class serializer_class:
        pass
