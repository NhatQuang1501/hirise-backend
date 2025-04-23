from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from users.choices import Role


class RoleBasedPermission(BasePermission):
    allowed_roles = []

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        try:
            role = get_role(request)
            return role in self.allowed_roles
        except AuthenticationFailed:
            return False


class IsAdmin(RoleBasedPermission):
    allowed_roles = ["admin"]


class IsApplicant(RoleBasedPermission):
    allowed_roles = ["applicant"]


class IsRecruiter(RoleBasedPermission):
    allowed_roles = ["recruiter"]


def get_role(request):
    jwt_auth = JWTAuthentication()
    header = jwt_auth.get_header(request)
    raw_token = jwt_auth.get_raw_token(header)
    validated_token = jwt_auth.get_validated_token(raw_token)
    user_role = validated_token.get("role")
    return user_role


# Custom permission
class IsOwnerOrAdmin(BasePermission):
    """
    Cho phép chỉ chủ sở hữu hoặc admin truy cập
    """

    def has_object_permission(self, request, view, obj):
        # Admin luôn có quyền
        if request.user.is_staff or request.user.role == Role.ADMIN:
            return True

        # Người dùng chỉ có thể truy cập đối tượng của chính họ
        return obj.id == request.user.id


class IsUserProfile(BasePermission):
    """
    Cho phép chỉ chủ sở hữu profile truy cập
    """

    def has_object_permission(self, request, view, obj):
        # Admin luôn có quyền
        if request.user.is_staff or request.user.role == Role.ADMIN:
            return True

        # Người dùng chỉ có thể truy cập profile của chính họ
        return obj.user.id == request.user.id


class IsRecruiter(BasePermission):
    """
    Chỉ cho phép nhà tuyển dụng thực hiện hành động
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Role.RECRUITER


class IsApplicant(BasePermission):
    """
    Chỉ cho phép ứng viên thực hiện hành động
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Role.APPLICANT


class IsAdmin(BasePermission):
    """
    Chỉ cho phép admin thực hiện hành động
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Role.ADMIN
