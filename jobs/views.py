from rest_framework import viewsets, filters, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Job, JobApplication
from .serializers import (
    JobListSerializer,
    JobDetailSerializer,
    JobCreateSerializer,
    JobUpdateSerializer,
    JobApplicationSerializer,
    JobApplicationCreateSerializer,
    JobApplicationUpdateSerializer,
)
from .permissions import (
    IsRecruiterOrReadOnly,
    IsJobOwner,
    IsApplicationOwnerOrJobRecruiter,
    IsApplicant,
    IsRecruiter,
)
from users.choices import JobStatus, ApplicationStatus, Role
from .mixins import JobViewMixin
from .filters import JobFilter, JobApplicationFilter


class JobViewSet(JobViewMixin, viewsets.ModelViewSet):
    """
    CRUD cho mô hình Job.
    """

    queryset = Job.objects.all()
    filterset_class = JobFilter  # Sử dụng custom filter thay vì filterset_fields
    search_fields = ["title", "description", "requirements", "company__name"]
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Job.objects.select_related("company").all()

        # Nếu là API công khai, chỉ hiển thị job đã đăng
        if self.action == "list" and not self.request.user.is_authenticated:
            queryset = queryset.filter(status=JobStatus.PUBLISHED)

        # Nếu là nhà tuyển dụng, chỉ hiển thị job của công ty họ
        elif self.action == "list" and self.request.user.role == "recruiter":
            company = self.request.user.recruiter_profile.company
            if company:
                queryset = queryset.filter(company=company)

        # Lọc theo tham số query
        keywords = self.request.query_params.get("keywords")
        if keywords:
            queryset = queryset.filter(
                Q(title__icontains=keywords)
                | Q(description__icontains=keywords)
                | Q(requirements__icontains=keywords)
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return JobCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return JobUpdateSerializer
        elif self.action == "retrieve":
            return JobDetailSerializer
        return JobListSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            self.permission_classes = [IsAuthenticated, IsRecruiter]
        elif self.action in ["publish", "close", "draft"]:
            self.permission_classes = [IsAuthenticated, IsJobOwner]
        else:
            self.permission_classes = [AllowAny]
        return super().get_permissions()

    def perform_create(self, serializer):
        # Gán công ty của nhà tuyển dụng
        company = self.request.user.recruiter_profile.company
        if not company:
            return Response(
                {"detail": "Bạn cần được gán cho một công ty trước khi tạo job"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save(company=company)

    @action(detail=True, methods=["patch"], url_path="publish")
    def publish(self, request, pk=None):
        """Chuyển job sang trạng thái đã đăng (published)"""
        job = self.get_object()

        # Kiểm tra trạng thái hiện tại
        if job.status == JobStatus.PUBLISHED:
            return Response(
                {"detail": "Job đã được đăng rồi"}, status=status.HTTP_400_BAD_REQUEST
            )
        elif job.status == JobStatus.CLOSED:
            return Response(
                {"detail": "Không thể đăng lại job đã đóng"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra các trường bắt buộc
        required_fields = ["title", "description", "job_type", "experience_level"]
        missing_fields = []

        for field in required_fields:
            if not getattr(job, field):
                missing_fields.append(field)

        if missing_fields:
            return Response(
                {"detail": f"Các trường sau là bắt buộc: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cập nhật trạng thái
        job.status = JobStatus.PUBLISHED
        job.save(update_fields=["status", "updated_at"])

        return Response(JobDetailSerializer(job).data)

    @action(detail=True, methods=["patch"], url_path="close")
    def close(self, request, pk=None):
        """Đóng job"""
        job = self.get_object()

        # Kiểm tra trạng thái hiện tại
        if job.status == JobStatus.CLOSED:
            return Response(
                {"detail": "Job has been closed"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Cập nhật trạng thái và ngày đóng
        job.status = JobStatus.CLOSED
        job.closed_date = timezone.now().date()
        job.save(update_fields=["status", "closed_date", "updated_at"])

        # Từ chối tất cả đơn ứng tuyển đang chờ xử lý
        JobApplication.objects.filter(
            job=job, status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING]
        ).update(
            status=ApplicationStatus.REJECTED, note="Job đã bị đóng bởi nhà tuyển dụng"
        )

        return Response(JobDetailSerializer(job).data)

    @action(detail=True, methods=["patch"], url_path="draft")
    def draft(self, request, pk=None):
        """Chuyển job về trạng thái nháp (draft)"""
        job = self.get_object()

        # Kiểm tra trạng thái hiện tại
        if job.status == JobStatus.DRAFT:
            return Response(
                {"detail": "Job đang ở trạng thái nháp rồi"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif job.status == JobStatus.CLOSED:
            return Response(
                {"detail": "Không thể chuyển job đã đóng về trạng thái nháp"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra xem job có đơn ứng tuyển không
        if job.applications.exists():
            return Response(
                {"detail": "Không thể chuyển về nháp vì job đã có đơn ứng tuyển"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cập nhật trạng thái
        job.status = JobStatus.DRAFT
        job.save(update_fields=["status", "updated_at"])

        return Response(JobDetailSerializer(job).data)

    @action(detail=True, methods=["get"], url_path="applications")
    def applications(self, request, pk=None):
        """Danh sách đơn ứng tuyển cho một job"""
        job = self.get_object()

        # Kiểm tra quyền truy cập - chỉ nhà tuyển dụng sở hữu job được xem
        self.check_object_permissions(request, job)

        applications = JobApplication.objects.filter(job=job).select_related(
            "applicant"
        )

        # Lọc theo status nếu có
        status_filter = request.query_params.get("status")
        if status_filter:
            applications = applications.filter(status=status_filter)

        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)


class JobApplicationViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    API cho JobApplication (đơn ứng tuyển).
    """

    queryset = JobApplication.objects.all()
    filterset_class = JobApplicationFilter
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = JobApplication.objects.select_related(
            "job", "job__company", "applicant"
        )

        # Nếu là ứng viên, chỉ xem đơn của họ
        if self.request.user.role == Role.APPLICANT:
            return queryset.filter(applicant=self.request.user)

        # Nếu là nhà tuyển dụng, chỉ xem đơn cho job của công ty họ
        elif self.request.user.role == Role.RECRUITER:
            company = self.request.user.recruiter_profile.company
            if company:
                return queryset.filter(job__company=company)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return JobApplicationCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return JobApplicationUpdateSerializer
        return JobApplicationSerializer

    def get_permissions(self):
        if self.action == "create":
            self.permission_classes = [IsAuthenticated, IsApplicant]
        elif self.action in ["update", "partial_update"]:
            self.permission_classes = [
                IsAuthenticated,
                IsApplicationOwnerOrJobRecruiter,
            ]
        else:
            self.permission_classes = [
                IsAuthenticated,
                IsApplicationOwnerOrJobRecruiter,
            ]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        job = serializer.validated_data["job"]

        # Kiểm tra xem job có đang mở không
        if job.status != JobStatus.PUBLISHED:
            return Response(
                {
                    "detail": "Không thể ứng tuyển vào job này do đã đóng hoặc chưa đăng tải"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Tạo đơn ứng tuyển
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response(
            JobApplicationSerializer(instance=serializer.instance).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    @action(detail=True, methods=["patch"], url_path="change-status")
    def change_status(self, request, pk=None):
        """Thay đổi trạng thái đơn ứng tuyển"""
        application = self.get_object()

        # Kiểm tra quyền - chỉ nhà tuyển dụng mới được thay đổi trạng thái
        if self.request.user.role != Role.RECRUITER:
            return Response(
                {
                    "detail": "Chỉ nhà tuyển dụng mới được thay đổi trạng thái đơn ứng tuyển"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy trạng thái mới từ request
        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"detail": "Trạng thái mới là bắt buộc"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cập nhật và xác thực
        serializer = JobApplicationUpdateSerializer(
            application,
            data={"status": new_status, "note": request.data.get("note")},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(JobApplicationSerializer(application).data)
