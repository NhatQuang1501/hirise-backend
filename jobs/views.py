from rest_framework import status, generics, filters, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django.db import transaction

from .models import Job, JobApplication, SavedJob
from .serializers import JobSerializer, JobApplicationSerializer, SavedJobSerializer
from .filters import JobFilter
from .permissions import (
    IsRecruiterOrReadOnly,
    IsJobOwner,
    IsApplicationOwnerOrJobRecruiter,
    IsApplicant,
    IsRecruiter,
)
from users.choices import JobStatus, ApplicationStatus, Role
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


# --- Job Views ---
class JobListView(generics.ListAPIView):
    """API để lấy danh sách các job"""

    serializer_class = JobSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = JobFilter
    search_fields = ["title", "description", "requirements", "company__name"]
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-created_at"]
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Lấy danh sách tất cả job",
        operation_summary="Lấy danh sách job",
        manual_parameters=[
            openapi.Parameter(
                "title",
                openapi.IN_QUERY,
                description="Tìm theo tiêu đề",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Lọc theo trạng thái",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "job_type",
                openapi.IN_QUERY,
                description="Lọc theo loại công việc",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "company",
                openapi.IN_QUERY,
                description="Tìm theo tên công ty",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "location",
                openapi.IN_QUERY,
                description="Tìm theo địa điểm",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Tìm kiếm tổng quát",
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={200: JobSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Job.objects.select_related("company").all()

        # Nếu là API công khai, chỉ hiển thị job đã đăng
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(status=JobStatus.PUBLISHED)

        # Nếu là nhà tuyển dụng, chỉ hiển thị job của công ty họ
        elif (
            self.request.user.is_authenticated
            and self.request.user.role == Role.RECRUITER
        ):
            company = self.request.user.recruiter_profile.company
            if company:
                queryset = queryset.filter(company=company)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class JobDetailView(generics.RetrieveAPIView):
    """API để xem chi tiết job"""

    queryset = Job.objects.select_related("company")
    serializer_class = JobSerializer
    permission_classes = [AllowAny]
    lookup_field = "id"

    @swagger_auto_schema(
        operation_description="Lấy thông tin chi tiết của một job",
        operation_summary="Chi tiết job",
        responses={200: JobSerializer(), 404: "Job không tồn tại"},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Ghi lại lượt xem
        from .models import JobView

        JobView.objects.create(
            job=instance, user=request.user if request.user.is_authenticated else None
        )

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class JobCreateView(generics.CreateAPIView):
    """API để tạo job mới"""

    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsRecruiter]

    @swagger_auto_schema(
        operation_description="Tạo một job mới (chỉ dành cho nhà tuyển dụng)",
        operation_summary="Tạo job mới",
        request_body=JobSerializer,
        responses={
            201: JobSerializer(),
            400: "Dữ liệu không hợp lệ",
            401: "Chưa xác thực",
            403: "Không có quyền",
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Gán công ty của nhà tuyển dụng
        user = self.request.user
        company = user.recruiter_profile.company
        if not company:
            raise serializers.ValidationError(
                {"detail": "Bạn cần được gán cho một công ty trước khi tạo job"}
            )
        serializer.save(company=company)


class JobUpdateView(generics.UpdateAPIView):
    """API để cập nhật job"""

    queryset = Job.objects.select_related("company")
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsJobOwner]
    lookup_field = "id"


class JobStatusUpdateView(APIView):
    """API để thay đổi trạng thái job"""

    permission_classes = [IsAuthenticated, IsJobOwner]

    def patch(self, request, id):
        job = get_object_or_404(Job, id=id)

        # Kiểm tra quyền truy cập
        if job.company != request.user.recruiter_profile.company:
            return Response(
                {"detail": "Bạn không có quyền thay đổi job này"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy trạng thái mới từ request
        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"detail": "Trạng thái mới là bắt buộc"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate trạng thái
        if new_status not in [s[0] for s in JobStatus.choices]:
            return Response(
                {"detail": f"Trạng thái '{new_status}' không hợp lệ"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate chuyển đổi trạng thái
        if job.status == JobStatus.CLOSED:
            return Response(
                {"detail": "Không thể thay đổi trạng thái của job đã đóng"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Xử lý chuyển từ PUBLISHED -> DRAFT
        if job.status == JobStatus.PUBLISHED and new_status == JobStatus.DRAFT:
            if job.applications.exists():
                return Response(
                    {"detail": "Không thể chuyển về nháp vì job đã có đơn ứng tuyển"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Xử lý chuyển sang PUBLISHED
        if new_status == JobStatus.PUBLISHED:
            required_fields = ["title", "description", "job_type", "experience_level"]
            missing_fields = []

            for field in required_fields:
                if not getattr(job, field):
                    missing_fields.append(field)

            if missing_fields:
                return Response(
                    {
                        "detail": f"Các trường sau là bắt buộc: {', '.join(missing_fields)}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Xử lý chuyển sang CLOSED
        if new_status == JobStatus.CLOSED:
            job.closed_date = timezone.now().date()

            # Từ chối các đơn ứng tuyển đang chờ xử lý
            with transaction.atomic():
                JobApplication.objects.filter(
                    job=job,
                    status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING],
                ).update(
                    status=ApplicationStatus.REJECTED,
                    note="Job đã bị đóng bởi nhà tuyển dụng",
                )

        # Cập nhật trạng thái job
        job.status = new_status
        job.save(
            update_fields=(
                ["status", "closed_date", "updated_at"]
                if new_status == JobStatus.CLOSED
                else ["status", "updated_at"]
            )
        )

        # Trả về job đã cập nhật
        serializer = JobSerializer(job, context={"request": request})
        return Response(serializer.data)


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


class JobSaveView(APIView):
    """API để lưu/bỏ lưu job"""

    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        """Lưu job"""
        job = get_object_or_404(Job, id=id)
        user = request.user

        # Kiểm tra đã lưu chưa
        if SavedJob.objects.filter(user=user, job=job).exists():
            return Response(
                {"detail": "Bạn đã lưu job này rồi"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Lưu job
        saved_job = SavedJob.objects.create(user=user, job=job)
        serializer = SavedJobSerializer(saved_job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, id):
        """Bỏ lưu job"""
        job = get_object_or_404(Job, id=id)
        user = request.user

        # Tìm và xóa saved job
        saved_job = SavedJob.objects.filter(user=user, job=job).first()
        if not saved_job:
            return Response(
                {"detail": "Bạn chưa lưu job này"}, status=status.HTTP_400_BAD_REQUEST
            )

        saved_job.delete()
        return Response(
            {"detail": "Đã bỏ lưu job thành công"}, status=status.HTTP_200_OK
        )


class JobStatisticsView(APIView):
    """API để lấy thống kê về job"""

    permission_classes = [IsAuthenticated, IsJobOwner]

    def get(self, request, id):
        job = get_object_or_404(Job, id=id)

        # Kiểm tra quyền
        if job.company != request.user.recruiter_profile.company:
            return Response(
                {"detail": "Bạn không có quyền xem thống kê của job này"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy thống kê
        stats = {
            # Tổng số đơn ứng tuyển
            "total_applications": job.applications.count(),
            # Phân loại theo trạng thái
            "pending_applications": job.applications.filter(
                status=ApplicationStatus.PENDING
            ).count(),
            "reviewing_applications": job.applications.filter(
                status=ApplicationStatus.REVIEWING
            ).count(),
            "interviewed_applications": job.applications.filter(
                status=ApplicationStatus.INTERVIEWED
            ).count(),
            "offered_applications": job.applications.filter(
                status=ApplicationStatus.OFFERED
            ).count(),
            "accepted_applications": job.applications.filter(
                status=ApplicationStatus.ACCEPTED
            ).count(),
            "rejected_applications": job.applications.filter(
                status=ApplicationStatus.REJECTED
            ).count(),
            # Thống kê views
            "total_views": job.views.count(),
            # Thời gian tồn tại
            "days_active": (timezone.now().date() - job.created_at.date()).days,
        }

        # Tính tỷ lệ chuyển đổi (conversion rate)
        if stats["total_views"] > 0:
            stats["application_rate"] = round(
                (stats["total_applications"] / stats["total_views"]) * 100, 2
            )
        else:
            stats["application_rate"] = 0

        return Response(stats)


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


# --- SavedJob Views ---
class SavedJobListView(generics.ListAPIView):
    """API để lấy danh sách job đã lưu của người dùng hiện tại"""

    serializer_class = SavedJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedJob.objects.filter(user=self.request.user).select_related(
            "job", "job__company"
        )
