from rest_framework import permissions
from users.choices import Role


class IsApplicantOwner(permissions.BasePermission):
    """
    Kiểm tra xem người dùng có phải là chủ sở hữu của đơn ứng tuyển không
    """

    def has_object_permission(self, request, view, obj):
        # Kiểm tra xem người dùng hiện tại có phải là ứng viên của đơn ứng tuyển này không
        return request.user.is_authenticated and obj.applicant.user == request.user


class IsCompanyOwner(permissions.BasePermission):
    """
    Kiểm tra xem người dùng có phải là công ty sở hữu công việc được ứng tuyển không
    """

    def has_object_permission(self, request, view, obj):
        # Kiểm tra xem người dùng hiện tại có phải là công ty sở hữu công việc này không
        return (
            request.user.is_authenticated
            and request.user.role == Role.COMPANY
            and obj.job.company.user == request.user
        )
