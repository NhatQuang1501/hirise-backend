from rest_framework import status, filters, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django.db import transaction

from jobs.models import Job, JobApplication, SavedJob, JobView
from jobs.serializers import JobSerializer, JobApplicationSerializer, SavedJobSerializer
from jobs.filters import JobFilter
from jobs.permissions import (
    IsRecruiterOrReadOnly,
    IsJobOwner,
    IsJobCreator,
    CanViewJob,
    IsApplicationOwnerOrJobRecruiter,
    IsApplicant,
    IsRecruiter,
)
from users.choices import JobStatus, ApplicationStatus, Role
from users.models import User
from users.utils import CustomPagination


class JobListView(APIView):
    """API để lấy danh sách các job"""

    permission_classes = [AllowAny]
    pagination_class = CustomPagination

    def get(self, request):
        # Lấy danh sách job
        queryset = Job.objects.select_related("company").all()

        # Applicant không thể xem job DRAFT
        if not request.user.is_authenticated or request.user.role == Role.APPLICANT:
            queryset = queryset.exclude(status=JobStatus.DRAFT)

        # Nếu là nhà tuyển dụng, chỉ hiển thị job của công ty họ và job PUBLISHED của công ty khác
        elif request.user.role == Role.RECRUITER:
            company = request.user.recruiter_profile.company
            if company:
                # Job của công ty hiện tại + các job PUBLISHED của công ty khác
                queryset = queryset.filter(
                    Q(company=company)
                    | ~Q(company=company) & ~Q(status=JobStatus.DRAFT)
                )
            else:
                # Nếu recruiter chưa có công ty, chỉ xem job PUBLISHED
                queryset = queryset.exclude(status=JobStatus.DRAFT)

        # Tìm kiếm
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(requirements__icontains=search)
                | Q(company__name__icontains=search)
            )

        # Filter
        filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
        filterset_class = JobFilter

        # Áp dụng filterset
        for backend in filter_backends:
            queryset = backend().filter_queryset(request, queryset, filterset_class)

        # Phân trang
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize và trả về kết quả
        serializer = JobSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)


class JobDetailView(APIView):
    """API để xem chi tiết job"""

    permission_classes = [CanViewJob]

    def get(self, request, pk):
        # Lấy thông tin job
        job = get_object_or_404(Job.objects.select_related("company"), id=pk)

        # Kiểm tra quyền xem job DRAFT
        if job.status == JobStatus.DRAFT:
            # Applicant không thể xem job DRAFT
            if not request.user.is_authenticated or request.user.role == Role.APPLICANT:
                return Response(
                    {"detail": "Bạn không có quyền xem job này"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Recruiter chỉ xem được job DRAFT của công ty họ
            if request.user.role == Role.RECRUITER:
                company = request.user.recruiter_profile.company
                if not company or job.company != company:
                    return Response(
                        {"detail": "Bạn không có quyền xem job này"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        # Ghi lại lượt xem
        JobView.objects.create(
            job=job, user=request.user if request.user.is_authenticated else None
        )

        # Trả về thông tin job
        serializer = JobSerializer(job, context={"request": request})
        return Response(serializer.data)


class JobCreateView(APIView):
    """API để tạo job mới"""

    permission_classes = [IsAuthenticated, IsRecruiter]

    def post(self, request):
        serializer = JobSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            # Gán công ty của nhà tuyển dụng
            user = request.user
            company = user.recruiter_profile.company
            if not company:
                return Response(
                    {"detail": "Bạn cần được gán cho một công ty trước khi tạo job"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Tạo job
            job = serializer.save(company=company)

            # Status mặc định là DRAFT nếu không được chỉ định
            if "status" not in request.data:
                job.status = JobStatus.DRAFT
                job.save(update_fields=["status"])

            # Trả về thông tin job
            serializer = JobSerializer(job, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # Xử lý lỗi
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobUpdateView(APIView):
    """API để cập nhật job"""

    permission_classes = [IsAuthenticated, IsJobCreator]

    def get_object(self, pk):
        job = get_object_or_404(Job.objects.select_related("company"), id=pk)
        self.check_object_permissions(self.request, job)
        return job

    def put(self, request, pk):
        job = self.get_object(pk)

        # Không thể cập nhật job đã đóng
        if job.status == JobStatus.CLOSED:
            return Response(
                {"detail": "Không thể cập nhật job đã đóng"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra nếu đang cập nhật job PUBLISHED
        was_published = job.status == JobStatus.PUBLISHED

        # Cập nhật job
        serializer = JobSerializer(job, data=request.data, context={"request": request})
        if serializer.is_valid():
            updated_job = serializer.save()

            # Job PUBLISHED khi chỉnh sửa sẽ chuyển về DRAFT trừ khi cố tình đóng job
            if (
                was_published
                and "status" not in request.data
                and updated_job.status != JobStatus.CLOSED
            ):
                updated_job.status = JobStatus.DRAFT
                updated_job.save(update_fields=["status"])

            # Trả về thông tin job
            serializer = JobSerializer(updated_job, context={"request": request})
            return Response(serializer.data)

        # Xử lý lỗi
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        job = self.get_object(pk)

        # Không thể cập nhật job đã đóng
        if job.status == JobStatus.CLOSED:
            return Response(
                {"detail": "Không thể cập nhật job đã đóng"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra nếu đang cập nhật job PUBLISHED
        was_published = job.status == JobStatus.PUBLISHED

        # Cập nhật job
        serializer = JobSerializer(
            job, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            updated_job = serializer.save()

            # Job PUBLISHED khi chỉnh sửa sẽ chuyển về DRAFT trừ khi cố tình closed hoặc vẫn giữ published
            if was_published and "status" not in request.data:
                updated_job.status = JobStatus.DRAFT
                updated_job.save(update_fields=["status"])

            # Trả về thông tin job
            serializer = JobSerializer(updated_job, context={"request": request})
            return Response(serializer.data)

        # Xử lý lỗi
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobDeleteView(APIView):
    """API để xóa job"""

    permission_classes = [IsAuthenticated, IsJobCreator]

    def delete(self, request, pk):
        job = get_object_or_404(Job, id=pk)

        # Kiểm tra quyền xóa
        self.check_object_permissions(request, job)

        # Xóa job
        job.delete()

        # Trả về kết quả
        return Response(
            {"detail": "Job đã được xóa thành công"}, status=status.HTTP_204_NO_CONTENT
        )


class JobStatusUpdateView(APIView):
    """API để thay đổi trạng thái job"""

    permission_classes = [IsAuthenticated, IsJobCreator]

    def patch(self, request, pk):
        job = get_object_or_404(Job, id=pk)

        # Kiểm tra quyền
        self.check_object_permissions(request, job)

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

        # Không thể thay đổi job đã đóng
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


class AutoCloseJobsView(APIView):
    """API to automatically close expired jobs"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Only admin has permission to call this API
        if request.user.role != Role.ADMIN:
            return Response(
                {"detail": "You don't have permission to perform this action"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get current date
        today = timezone.now().date()

        # Find jobs that need to be closed
        expired_jobs = Job.objects.filter(
            status=JobStatus.PUBLISHED, closed_date__lte=today
        )

        # Close jobs and reject pending applications
        closed_count = 0
        with transaction.atomic():
            for job in expired_jobs:
                job.status = JobStatus.CLOSED
                job.save(update_fields=["status", "updated_at"])

                # Reject pending applications
                JobApplication.objects.filter(
                    job=job,
                    status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING],
                ).update(
                    status=ApplicationStatus.REJECTED,
                    note="Job was automatically closed because it reached its expiration date",
                )

                closed_count += 1

        # Return result
        return Response(
            {
                "detail": f"{closed_count} jobs have been automatically closed",
                "closed_count": closed_count,
            }
        )


class JobSaveView(APIView):
    """API to save/unsave a job"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Save job"""
        job = get_object_or_404(Job, id=pk)
        user = request.user

        # Check if already saved
        if SavedJob.objects.filter(user=user, job=job).exists():
            return Response(
                {"detail": "You have already saved this job"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save job
        saved_job = SavedJob.objects.create(user=user, job=job)
        serializer = SavedJobSerializer(saved_job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        """Unsave job"""
        job = get_object_or_404(Job, id=pk)
        user = request.user

        # Find and delete saved job
        saved_job = SavedJob.objects.filter(user=user, job=job).first()
        if not saved_job:
            return Response(
                {"detail": "You haven't saved this job"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        saved_job.delete()
        return Response(
            {"detail": "Job has been unsaved successfully"}, status=status.HTTP_200_OK
        )


class JobStatisticsView(APIView):
    """API to get statistics about a job"""

    permission_classes = [IsAuthenticated, IsJobOwner]

    def get(self, request, pk):
        job = get_object_or_404(Job, id=pk)

        # Check permission
        self.check_object_permissions(request, job)

        # Get statistics
        stats = {
            # Total applications
            "total_applications": job.applications.count(),
            # Categorize by status
            "pending_applications": job.applications.filter(
                status=ApplicationStatus.PENDING
            ).count(),
            "reviewing_applications": job.applications.filter(
                status=ApplicationStatus.REVIEWING
            ).count(),
            "accepted_applications": job.applications.filter(
                status=ApplicationStatus.ACCEPTED
            ).count(),
            "rejected_applications": job.applications.filter(
                status=ApplicationStatus.REJECTED
            ).count(),
            # View statistics
            "total_views": job.views.count(),
            # Days active
            "days_active": (timezone.now().date() - job.created_at.date()).days,
        }

        # Calculate conversion rate
        if stats["total_views"] > 0:
            stats["application_rate"] = round(
                (stats["total_applications"] / stats["total_views"]) * 100, 2
            )
        else:
            stats["application_rate"] = 0

        return Response(stats)


class SavedJobListView(APIView):
    """API to get list of saved jobs"""

    permission_classes = [AllowAny]  # Allow anyone to view saved jobs list
    pagination_class = CustomPagination

    def get(self, request):
        # Get user ID from query params, default to current user if authenticated
        user_id = request.query_params.get("user_id")

        if user_id:
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Get saved jobs for the specified user
            queryset = SavedJob.objects.filter(user=target_user)

        elif request.user.is_authenticated:
            # Get saved jobs for the current user
            queryset = SavedJob.objects.filter(user=request.user)

        else:
            # If no user_id and not authenticated, return error
            return Response(
                {"detail": "You must specify a user_id or be authenticated"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Optimize queries
        queryset = queryset.select_related("job", "job__company")

        # Apply filters
        job_title = request.query_params.get("job_title")
        if job_title:
            queryset = queryset.filter(job__title__icontains=job_title)

        company_name = request.query_params.get("company")
        if company_name:
            queryset = queryset.filter(job__company__name__icontains=company_name)

        # Order by creation date (newest first by default)
        ordering = request.query_params.get("ordering", "-created_at")
        queryset = queryset.order_by(ordering)

        # Pagination
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize and return
        serializer = SavedJobSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)
