from rest_framework import permissions
from users.choices import Role, JobStatus


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
            and obj.company == request.user.recruiter_profile.company
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


class IsJobCreator(permissions.BasePermission):
    """
    Chỉ cho phép người tạo job chỉnh sửa hoặc xóa job đó.
    """

    def has_object_permission(self, request, view, obj):
        # Chỉ người tạo job mới có quyền chỉnh sửa hoặc xóa
        return (
            request.user.is_authenticated
            and request.user.role == Role.RECRUITER
            and obj.company == request.user.recruiter_profile.company
        )


class CanViewJob(permissions.BasePermission):
    """
    Quyền xem job dựa trên trạng thái.
    Job DRAFT chỉ có thể được xem bởi người tạo hoặc admin.
    Job PUBLISHED và CLOSED có thể được xem bởi tất cả mọi người.
    """

    def has_object_permission(self, request, view, obj):
        # Admin luôn có quyền xem
        if request.user.is_authenticated and request.user.role == Role.ADMIN:
            return True

        # Nhà tuyển dụng sở hữu job luôn có quyền xem
        if (
            request.user.is_authenticated
            and request.user.role == Role.RECRUITER
            and obj.company == request.user.recruiter_profile.company
        ):
            return True

        # Nếu job là DRAFT, chỉ owner mới xem được (đã xử lý ở trên)
        if obj.status == JobStatus.DRAFT:
            return False

        # Các job khác có thể xem bởi mọi người
        return True


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


class IsRecruiter(permissions.BasePermission):
    """
    Chỉ cho phép nhà tuyển dụng thực hiện hành động.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Role.RECRUITER
