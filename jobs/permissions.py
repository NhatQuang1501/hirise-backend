from rest_framework import permissions
from users.choices import Role, JobStatus


class IsCompanyOrReadOnly(permissions.BasePermission):
    """
    Cho phép công ty sửa đổi, những người khác chỉ được xem.
    """

    def has_permission(self, request, view):
        # Cho phép GET, HEAD, OPTIONS cho tất cả người dùng
        if request.method in permissions.SAFE_METHODS:
            return True

        # Yêu cầu phương thức khác chỉ cho công ty
        return request.user.is_authenticated and request.user.role == Role.COMPANY

    def has_object_permission(self, request, view, obj):
        # Cho phép GET, HEAD, OPTIONS cho tất cả người dùng
        if request.method in permissions.SAFE_METHODS:
            return True

        # Công ty chỉ sửa job của họ
        return (
            request.user.is_authenticated
            and request.user.role == Role.COMPANY
            and obj.company == request.user.company_profile
        )


class IsJobOwner(permissions.BasePermission):
    """
    Chỉ cho phép công ty sở hữu job thao tác với job.
    """

    def has_object_permission(self, request, view, obj):
        # Chỉ công ty được thao tác
        if not request.user.is_authenticated or request.user.role != Role.COMPANY:
            return False

        # Kiểm tra xem công ty có sở hữu job không
        return obj.company == request.user.company_profile


class IsJobCreator(permissions.BasePermission):
    """
    Chỉ cho phép công ty sở hữu job để chỉnh sửa hoặc xóa job đó.
    """

    def has_object_permission(self, request, view, obj):
        # Chỉ công ty sở hữu job được chỉnh sửa hoặc xóa
        return (
            request.user.is_authenticated
            and request.user.role == Role.COMPANY
            and obj.company == request.user.company_profile
        )


class CanViewJob(permissions.BasePermission):
    """
    Quyền xem job dựa trên trạng thái.
    Job DRAFT chỉ có thể được xem bởi công ty sở hữu job hoặc admin.
    Job PUBLISHED và CLOSED có thể được xem bởi tất cả mọi người.
    """

    def has_object_permission(self, request, view, obj):
        # Admin luôn có quyền xem
        if request.user.is_authenticated and request.user.role == Role.ADMIN:
            return True

        # Công ty sở hữu job luôn có quyền xem
        if (
            request.user.is_authenticated
            and request.user.role == Role.COMPANY
            and obj.company == request.user.company_profile
        ):
            return True

        # Nếu job là DRAFT, chỉ công ty sở hữu mới xem được (đã xử lý ở trên)
        if obj.status == JobStatus.DRAFT:
            return False

        # Các job khác có thể xem bởi mọi người
        return True


class IsApplicationOwnerOrJobCompany(permissions.BasePermission):
    """
    Cho phép ứng viên xem đơn của họ, công ty xem và cập nhật đơn cho job của họ.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # Ứng viên chỉ xem được đơn của mình
        if request.user.role == Role.APPLICANT:
            return (
                obj.applicant.user == request.user
                and request.method in permissions.SAFE_METHODS
            )

        # Công ty xem và cập nhật đơn cho job của họ
        if request.user.role == Role.COMPANY:
            return obj.job.company == request.user.company_profile

        # Admin có toàn quyền
        if request.user.role == Role.ADMIN:
            return True

        return False


class IsApplicant(permissions.BasePermission):
    """
    Chỉ cho phép ứng viên thực hiện hành động.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Role.APPLICANT


class IsCompany(permissions.BasePermission):
    """
    Chỉ cho phép công ty thực hiện hành động.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Role.COMPANY


class IsSavedJobOwner(permissions.BasePermission):
    """
    Chỉ cho phép chủ sở hữu của saved job thao tác.
    """

    def has_object_permission(self, request, view, obj):
        return (
            request.user.is_authenticated
            and request.user.role == Role.APPLICANT
            and obj.applicant == request.user.applicant_profile
        )
