"""
Core RBAC Permission Classes for DRF
"""
from rest_framework.permissions import BasePermission
from apps.accounts.models import User


class IsSuperAdmin(BasePermission):
    """Only Super Admins."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == User.Role.SUPER_ADMIN
        )


class IsSchoolAdminOrAbove(BasePermission):
    """School Admin or Super Admin."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]
        )


class IsExamHeadOrAbove(BasePermission):
    """
    School Admin or Super Admin.
    NOTE: There is currently no distinct EXAM_HEAD role.
    This class is functionally identical to IsSchoolAdminOrAbove.
    It is kept for semantic clarity and future extensibility.
    """
    ALLOWED = [User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN]

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in self.ALLOWED
        )


class IsTeacherOrAbove(BasePermission):
    """Teacher, School Admin, or Super Admin (can enter marks)."""
    ALLOWED = [
        User.Role.SUPER_ADMIN,
        User.Role.SCHOOL_ADMIN,
        User.Role.TEACHER,   # FIX: was missing from the original list
    ]

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in self.ALLOWED
        )


class IsViewerOrAbove(BasePermission):
    """Any authenticated role."""
    def has_permission(self, request, view):
        return request.user.is_authenticated


class IsSchoolScoped(BasePermission):
    """Ensures user belongs to a school (not a floating Super Admin viewing all)."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.school is not None or request.user.is_super_admin)
        )


class ReadOnly(BasePermission):
    """Allow GET/HEAD/OPTIONS only."""
    def has_permission(self, request, view):
        return request.method in ('GET', 'HEAD', 'OPTIONS')
