"""
Accounts serializers
"""
from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'role', 'role_display', 'school', 'school_name',
            'phone', 'profile_picture', 'is_active', 'date_joined',
        ]
        # SECURITY: role, school, is_active must never be writable by the user themselves.
        # These can only be changed by a Super Admin through dedicated admin endpoints.
        read_only_fields = [
            'id', 'date_joined', 'role', 'school', 'is_active', 'is_staff',
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Safe serializer for PATCH /api/v1/auth/me/.
    Only allows updating non-sensitive personal fields.
    role, school, is_active, is_staff, username are all read-only here.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError('New passwords do not match.')
        return data
