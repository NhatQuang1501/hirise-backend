from rest_framework import permissions
from users.enums import Role
from jobs.models import Job


class IsRecruiterOrReadOnly(permissions.BasePermission):
    """
    Cho phép nhà tuyển dụng sửa đổi, những người khác chỉ được xem.
    """

    def has_permission(self, request, view):
        # Cho phép GET, HEAD, OPTIONS cho tất cả người dùng
        if request.method in permissions.SAFE_METHODS:
            return True

        # Yêu cầu phương thức khác chỉ cho nhà tuyển dụng
        return request.user.is_authenticated and request.user.role == Role.RECRUITER

    def has_object_permission(self, request, view, obj):
        # Cho phép GET, HEAD, OPTIONS cho tất cả người dùng
        if request.method in permissions.SAFE_METHODS:
            return True

        # Nhà tuyển dụng chỉ sửa job của công ty họ
        return (
            request.user.is_authenticated
            and request.user.role == Role.RECRUITER
            and obj.company in request.user.recruiter_profile.company
        )


class IsJobOwner(permissions.BasePermission):
    """
    Chỉ cho phép nhà tuyển dụng sở hữu job thao tác với job.
    """

    def has_object_permission(self, request, view, obj):
        # Chỉ nhà tuyển dụng được thao tác
        if not request.user.is_authenticated or request.user.role != Role.RECRUITER:
            return False

        # Kiểm tra xem nhà tuyển dụng có thuộc công ty sở hữu job không
        return obj.company == request.user.recruiter_profile.company


class IsApplicationOwnerOrJobRecruiter(permissions.BasePermission):
    """
    Cho phép ứng viên xem đơn của họ, nhà tuyển dụng xem và cập nhật đơn cho job của họ.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # Ứng viên chỉ xem được đơn của mình
        if request.user.role == Role.APPLICANT:
            return (
                obj.applicant == request.user
                and request.method in permissions.SAFE_METHODS
            )

        # Nhà tuyển dụng xem và cập nhật đơn cho job của công ty họ
        if request.user.role == Role.RECRUITER:
            return obj.job.company == request.user.recruiter_profile.company

        return False


class IsApplicant(permissions.BasePermission):
    """
    Chỉ cho phép ứng viên thực hiện hành động.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Role.APPLICANT


class IsRecruiter(permissions.BasePermission):
    """
    Chỉ cho phép nhà tuyển dụng thực hiện hành động.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Role.RECRUITER
