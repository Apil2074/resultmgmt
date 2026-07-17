"""
Accounts REST API — JWT login/logout, user management
"""
import logging

from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from core.permissions import IsSuperAdmin, IsSchoolAdminOrAbove
from .models import User
from .serializers import UserSerializer, ChangePasswordSerializer, ProfileUpdateSerializer

logger = logging.getLogger(__name__)


class LoginAPIView(APIView):
    """
    API Login endpoint.
    Rate-limited by django-ratelimit (10 attempts/min per IP).
    """
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True))
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)

        if user and user.is_active:
            if user.school and not user.is_super_admin and not user.school.has_active_subscription():
                return Response(
                    {'error': 'Your school subscription has expired. Please contact the Super Admin.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
            })
        logger.warning("Failed API login attempt for username='%s'", username)
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logged out successfully'})
        except Exception:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({'error': 'Wrong password'}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'message': 'Password changed successfully'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeAPIView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update the currently authenticated user's profile.
    SECURITY: Uses ProfileUpdateSerializer for write operations so that
    role, school, is_active, username cannot be self-modified.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        # Read-only GETs return the full user info; writes use the safe subset
        if self.request.method in ('PUT', 'PATCH'):
            return ProfileUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user


class UserListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            # SECURITY: Only school admins and above can list users.
            # Previously any authenticated user could list all users in their school.
            return [IsSchoolAdminOrAbove()]
        return [IsSuperAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_super_admin:
            return User.objects.all()
        return User.objects.filter(school=user.school)

    def perform_create(self, serializer):
        serializer.save()
