from rest_framework.permissions import BasePermission, SAFE_METHODS
from users.choices import Role


class IsOwnerOrAdmin(BasePermission):
    """Allow only owners or admins to access"""

    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and (
            request.user.id == obj.id or request.user.role == Role.ADMIN
        )


class RoleBasedPermission(BasePermission):
    allowed_role = None

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role == self.allowed_role


class IsApplicant(RoleBasedPermission):
    allowed_role = Role.APPLICANT


class IsCompany(RoleBasedPermission):
    allowed_role = Role.COMPANY


class IsAdmin(RoleBasedPermission):
    allowed_role = Role.ADMIN


class IsOwnerOrReadOnly(BasePermission):
    """
    Custom permission to only allow owners of a profile to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated request
        if request.method in ["GET"]:
            return True

        # Write permissions are only allowed to the owner
        return obj.user.id == request.user.id
