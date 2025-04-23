from rest_framework import status, generics, filters, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django.db import transaction

from jobs.models import Job, JobApplication, SavedJob
from jobs.serializers import JobSerializer, JobApplicationSerializer, SavedJobSerializer
from jobs.filters import JobFilter
from jobs.permissions import (
    IsRecruiterOrReadOnly,
    IsJobOwner,
    IsApplicationOwnerOrJobRecruiter,
    IsApplicant,
    IsRecruiter,
)
from users.choices import JobStatus, ApplicationStatus, Role
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


class JobApplyView(APIView):
    """API để ứng tuyển vào job"""

    permission_classes = [IsAuthenticated, IsApplicant]

    @swagger_auto_schema(
        operation_description="Ứng tuyển vào một job (chỉ dành cho ứng viên)",
        operation_summary="Ứng tuyển job",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "note": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Ghi chú kèm theo đơn ứng tuyển",
                )
            },
        ),
        responses={
            201: JobApplicationSerializer(),
            400: "Lỗi khi ứng tuyển",
            401: "Chưa xác thực",
            403: "Không có quyền",
            404: "Job không tồn tại",
        },
    )
    def post(self, request, id):
        job = get_object_or_404(Job, id=id)
        user = request.user

        # Kiểm tra job có đang mở không
        if job.status != JobStatus.PUBLISHED:
            return Response(
                {
                    "detail": "Không thể ứng tuyển vào job này do đã đóng hoặc chưa đăng tải"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra người dùng đã ứng tuyển chưa
        if JobApplication.objects.filter(applicant=user, job=job).exists():
            return Response(
                {"detail": "Bạn đã ứng tuyển vào job này rồi"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Tạo đơn ứng tuyển
        note = request.data.get("note", "")
        application = JobApplication.objects.create(
            applicant=user, job=job, status=ApplicationStatus.PENDING, note=note
        )

        # Trả về thông tin đơn ứng tuyển
        serializer = JobApplicationSerializer(application)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# --- Application Views ---
class ApplicationListView(generics.ListAPIView):
    """API để lấy danh sách các đơn ứng tuyển"""

    serializer_class = JobApplicationSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "job"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = JobApplication.objects.select_related(
            "job", "job__company", "applicant"
        )

        # Nếu là ứng viên, chỉ xem đơn của họ
        if user.role == Role.APPLICANT:
            return queryset.filter(applicant=user)

        # Nếu là nhà tuyển dụng, chỉ xem đơn cho job của công ty họ
        elif user.role == Role.RECRUITER:
            company = user.recruiter_profile.company
            if company:
                return queryset.filter(job__company=company)

        # Admin xem tất cả
        return queryset


class ApplicationDetailView(generics.RetrieveAPIView):
    """API để xem chi tiết đơn ứng tuyển"""

    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsApplicationOwnerOrJobRecruiter]
    lookup_field = "id"

    def get_queryset(self):
        return JobApplication.objects.select_related("job", "job__company", "applicant")


class ApplicationUpdateView(generics.UpdateAPIView):
    """API để cập nhật trạng thái đơn ứng tuyển"""

    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsApplicationOwnerOrJobRecruiter]
    lookup_field = "id"

    @swagger_auto_schema(
        operation_description="Cập nhật trạng thái đơn ứng tuyển (chỉ dành cho nhà tuyển dụng)",
        operation_summary="Cập nhật đơn ứng tuyển",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["status"],
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Trạng thái mới của đơn ứng tuyển",
                    enum=[status[0] for status in ApplicationStatus.choices],
                ),
                "note": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Ghi chú khi cập nhật trạng thái",
                ),
            },
        ),
        responses={
            200: JobApplicationSerializer(),
            400: "Dữ liệu không hợp lệ hoặc chuyển đổi trạng thái không được phép",
            401: "Chưa xác thực",
            403: "Không có quyền hoặc job đã đóng",
            404: "Đơn ứng tuyển không tồn tại",
        },
        security=[{"Bearer": []}],
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        queryset = JobApplication.objects.select_related(
            "job", "job__company", "applicant"
        )

        # Nhà tuyển dụng chỉ cập nhật đơn cho job của công ty họ
        if user.role == Role.RECRUITER:
            company = user.recruiter_profile.company
            if company:
                return queryset.filter(job__company=company)

        # Ứng viên không thể cập nhật đơn
        return queryset.none()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()

        # Chỉ nhà tuyển dụng mới được cập nhật trạng thái
        if request.user.role != Role.RECRUITER:
            return Response(
                {
                    "detail": "Chỉ nhà tuyển dụng mới được thay đổi trạng thái đơn ứng tuyển"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Kiểm tra job có đang mở không
        if instance.job.status == JobStatus.CLOSED and "status" in request.data:
            new_status = request.data.get("status")
            if new_status != ApplicationStatus.REJECTED:
                return Response(
                    {"detail": "Không thể cập nhật đơn ứng tuyển cho job đã đóng"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Gửi email thông báo (có thể implement sau)
        # from .services import JobApplicationService
        # JobApplicationService.notify_applicant_status_change(instance)

        return Response(serializer.data)
