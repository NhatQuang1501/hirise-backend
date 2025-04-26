from rest_framework import status, filters, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
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
    IsSavedJobOwner,
)
from users.choices import JobStatus, ApplicationStatus, Role
from users.models import User, ApplicantProfile
from users.utils import CustomPagination


# --- Job Views ---
class JobListView(APIView):
    """API to get list of jobs"""

    permission_classes = [AllowAny]
    pagination_class = CustomPagination

    def get(self, request):
        # Lấy danh sách job với các quan hệ cần thiết
        queryset = Job.objects.select_related("company", "recruiter").all()

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
    """API to view job details"""

    permission_classes = [CanViewJob]

    def get(self, request, pk):
        # Lấy thông tin job với các quan hệ cần thiết
        job = get_object_or_404(
            Job.objects.select_related("company", "recruiter"), id=pk
        )

        # Kiểm tra quyền xem job
        self.check_object_permissions(request, job)

        # Ghi lại lượt xem
        JobView.objects.create(
            job=job, user=request.user if request.user.is_authenticated else None
        )

        # Trả về thông tin job
        serializer = JobSerializer(job, context={"request": request})
        return Response(serializer.data)


class JobCreateView(APIView):
    """API to create a new job"""

    permission_classes = [IsAuthenticated, IsRecruiter]

    def post(self, request):
        serializer = JobSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            # Gán công ty của nhà tuyển dụng
            user = request.user
            company = user.recruiter_profile.company
            if not company:
                return Response(
                    {
                        "detail": "You need to be assigned to a company before creating a job"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Tạo job
            job = serializer.save()

            # Trả về thông tin job
            serializer = JobSerializer(job, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # Xử lý lỗi
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobUpdateView(APIView):
    """API to update a job"""

    permission_classes = [IsAuthenticated, IsJobCreator]

    def get_object(self, pk):
        job = get_object_or_404(
            Job.objects.select_related("company", "recruiter"), id=pk
        )
        self.check_object_permissions(self.request, job)
        return job

    def put(self, request, pk):
        job = self.get_object(pk)

        # Không thể cập nhật job đã đóng
        if job.status == JobStatus.CLOSED:
            return Response(
                {"detail": "Cannot update a closed job"},
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
                {"detail": "Cannot update a closed job"},
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
    """API to delete a job"""

    permission_classes = [IsAuthenticated, IsJobCreator]

    def delete(self, request, pk):
        # Lấy thông tin job với các quan hệ cần thiết
        job = get_object_or_404(
            Job.objects.select_related("company", "recruiter"), id=pk
        )

        # Kiểm tra quyền xóa
        self.check_object_permissions(request, job)

        # Xóa job
        job.delete()

        # Thông báo xóa thành công
        return Response(
            {"detail": "Job has been successfully deleted"},
            status=status.HTTP_204_NO_CONTENT,
        )


class JobStatusUpdateView(APIView):
    """API to update job status"""

    permission_classes = [IsAuthenticated, IsJobCreator]

    def patch(self, request, pk):
        # Lấy thông tin job với các quan hệ cần thiết
        job = get_object_or_404(
            Job.objects.select_related("company", "recruiter"), id=pk
        )

        # Kiểm tra quyền thay đổi trạng thái
        self.check_object_permissions(request, job)

        # Kiểm tra trạng thái mới có được cung cấp không
        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"detail": "New job status is not provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra trạng thái mới hợp lệ
        if new_status not in dict(JobStatus.choices):
            return Response(
                {"detail": f"Status '{new_status}' is not valid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Không thể thay đổi trạng thái job đã đóng
        if job.status == JobStatus.CLOSED:
            return Response(
                {"detail": "Cannot change status of a closed job"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra các trường bắt buộc khi publish
        if new_status == JobStatus.PUBLISHED:
            required_fields = ["title", "description", "job_type", "experience_level"]
            missing_fields = []

            for field in required_fields:
                if not getattr(job, field):
                    missing_fields.append(field)

            if missing_fields:
                return Response(
                    {
                        "detail": f"Cannot publish job. Missing required fields: {', '.join(missing_fields)}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Thay đổi trạng thái
        if job.status != new_status:
            # Nếu closed job, cập nhật closed_date
            if new_status == JobStatus.CLOSED:
                job.closed_date = timezone.now().date()
                job.save(update_fields=["status", "closed_date", "updated_at"])

                # Từ chối các đơn ứng tuyển chưa xử lý
                with transaction.atomic():
                    pending_applications = job.applications.filter(
                        status__in=[
                            ApplicationStatus.PENDING,
                            ApplicationStatus.REVIEWING,
                        ]
                    )
                    pending_applications.update(
                        status=ApplicationStatus.REJECTED,
                        note="Job has been closed by recruiter",
                    )
            else:
                job.save(update_fields=["status", "updated_at"])

        # Serialize và trả về kết quả
        serializer = JobSerializer(job, context={"request": request})
        return Response(serializer.data)


class AutoCloseJobsView(APIView):
    """API to automatically close expired jobs"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Only admin has permission to call this API
        if request.user.role != Role.ADMIN:
            return Response(
                {"detail": "Only admin can perform this function"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get expiry days from request, default to 30 days
        try:
            expiry_days = int(request.data.get("expiry_days", 30))
            if expiry_days <= 0:
                return Response(
                    {"detail": "Invalid expiry days value"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"detail": "Invalid expiry days value"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get expired jobs
        today = timezone.now().date()
        expiry_date = today - timezone.timedelta(days=expiry_days)

        # Tìm các job hết hạn để đóng
        jobs_to_close = (
            Job.objects.filter(status=JobStatus.PUBLISHED)
            .filter(
                # Jobs đã quá date đóng
                Q(closed_date__isnull=False, closed_date__lt=today)
                |
                # Jobs đã tạo quá lâu mà không set closed_date
                Q(
                    closed_date__isnull=True,
                    updated_at__date__lte=expiry_date,
                    created_at__date__lte=expiry_date,
                )
            )
            .select_related("company", "recruiter")
            .prefetch_related("applications")
        )

        # Close expired jobs
        jobs_closed = 0
        for job in jobs_to_close:
            with transaction.atomic():
                # Update job status
                job.status = JobStatus.CLOSED
                job.closed_date = today
                job.save(update_fields=["status", "closed_date", "updated_at"])

                # Reject pending applications
                job.applications.filter(
                    status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING]
                ).update(
                    status=ApplicationStatus.REJECTED,
                    note="Job has been closed automatically due to expiration",
                )

                jobs_closed += 1

        # Return statistics
        return Response(
            {
                "jobs_closed": jobs_closed,
                "expiry_days": expiry_days,
                "expiry_date": expiry_date.isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class JobSaveView(APIView):
    """API to save/unsave a job"""

    permission_classes = [IsAuthenticated, IsApplicant]

    def post(self, request, pk):
        # Kiểm tra job tồn tại
        job = get_object_or_404(Job, id=pk)

        # Chỉ có thể lưu job được publish
        if job.status != JobStatus.PUBLISHED:
            return Response(
                {"detail": "Cannot save a job that is not published"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Lấy applicant profile
        applicant_profile = request.user.applicant_profile

        # Kiểm tra đã lưu chưa
        if SavedJob.objects.filter(applicant=applicant_profile, job=job).exists():
            return Response(
                {"detail": "Job has already been saved"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Lưu job
        saved_job = SavedJob.objects.create(applicant=applicant_profile, job=job)

        # Trả về thông tin saved job
        serializer = SavedJobSerializer(saved_job, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        # Kiểm tra job tồn tại
        job = get_object_or_404(Job, id=pk)

        # Lấy applicant profile
        applicant_profile = request.user.applicant_profile

        # Kiểm tra đã lưu chưa
        saved_job = SavedJob.objects.filter(
            applicant=applicant_profile, job=job
        ).first()
        if not saved_job:
            return Response(
                {"detail": "Job has not been saved"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Xóa saved job
        saved_job.delete()

        # Trả về thông báo thành công
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobStatisticsView(APIView):
    """API to get statistics about a job"""

    permission_classes = [IsAuthenticated, IsJobOwner]

    def get(self, request, pk):
        # Kiểm tra job tồn tại và quyền xem
        job = get_object_or_404(
            Job.objects.select_related("company", "recruiter").prefetch_related(
                "views", "applications", "saved_by"
            ),
            id=pk,
        )

        # Kiểm tra quyền xem thống kê
        self.check_object_permissions(request, job)

        # Lấy số lượng view, application, saved
        total_views = job.views.count()
        total_applications = job.applications.count()
        total_saved = job.saved_by.count()

        # Lấy thống kê theo ngày trong 30 ngày gần nhất
        days_to_look_back = 30
        today = timezone.now().date()
        start_date = today - timezone.timedelta(
            days=days_to_look_back - 1
        )  # Including today

        # Chuẩn bị dữ liệu theo ngày
        date_stats = {}
        for i in range(days_to_look_back):
            current_date = start_date + timezone.timedelta(days=i)
            date_stats[current_date.isoformat()] = {
                "views": 0,
                "applications": 0,
                "saved": 0,
            }

        # Tính view theo ngày
        views_by_day = (
            job.views.filter(viewed_at__date__gte=start_date)
            .values("viewed_at__date")
            .annotate(count=Count("id"))
        )
        for item in views_by_day:
            date_key = item["viewed_at__date"].isoformat()
            if date_key in date_stats:
                date_stats[date_key]["views"] = item["count"]

        # Tính application theo ngày
        applications_by_day = (
            job.applications.filter(created_at__date__gte=start_date)
            .values("created_at__date")
            .annotate(count=Count("id"))
        )
        for item in applications_by_day:
            date_key = item["created_at__date"].isoformat()
            if date_key in date_stats:
                date_stats[date_key]["applications"] = item["count"]

        # Tính saved theo ngày
        saved_by_day = (
            job.saved_by.filter(created_at__date__gte=start_date)
            .values("created_at__date")
            .annotate(count=Count("id"))
        )
        for item in saved_by_day:
            date_key = item["created_at__date"].isoformat()
            if date_key in date_stats:
                date_stats[date_key]["saved"] = item["count"]

        # Trả về kết quả
        return Response(
            {
                "job_id": job.id,
                "job_title": job.title,
                "job_status": job.status,
                "totals": {
                    "views": total_views,
                    "applications": total_applications,
                    "saved": total_saved,
                },
                "daily_stats": date_stats,
            },
            status=status.HTTP_200_OK,
        )


class SavedJobListView(APIView):
    """API to get list of saved jobs"""

    permission_classes = [IsAuthenticated, IsApplicant]
    pagination_class = CustomPagination

    def get(self, request):
        # Lấy danh sách saved jobs của applicant hiện tại
        queryset = (
            SavedJob.objects.filter(applicant=request.user.applicant_profile)
            .select_related("job", "job__company")
            .order_by("-created_at")
        )

        # Phân trang
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize và trả về kết quả
        serializer = SavedJobSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)


class ApplicantSavedJobsView(APIView):
    """API to get list of saved jobs for a specific applicant"""

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, applicant_id):
        # Kiểm tra quyền xem
        if str(request.user.id) != applicant_id and request.user.role != Role.ADMIN:
            return Response(
                {
                    "detail": "You don't have permission to view this applicant's saved jobs"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy applicant profile
        applicant_profile = get_object_or_404(
            ApplicantProfile.objects.select_related("user"), user_id=applicant_id
        )

        # Lấy danh sách saved jobs
        queryset = (
            SavedJob.objects.filter(applicant=applicant_profile)
            .select_related("job", "job__company")
            .order_by("-created_at")
        )

        # Phân trang
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize và trả về kết quả
        serializer = SavedJobSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)
