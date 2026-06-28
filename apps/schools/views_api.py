from rest_framework import viewsets; from rest_framework.permissions import IsAuthenticated; from .models import School, AcademicSession; from .serializers import SchoolSerializer, SessionSerializer; from core.mixins import SchoolScopedMixin
class SchoolViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
class SessionViewSet(SchoolScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = AcademicSession.objects.all()
    serializer_class = SessionSerializer
