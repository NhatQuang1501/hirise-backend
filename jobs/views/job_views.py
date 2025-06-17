from rest_framework import status, filters, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone
from django.db import transaction

from jobs.models import (
    Job,
    SavedJob,
    JobStatistics,
    CompanyStatistics,
)
from jobs.serializers import (
    JobSerializer,
    SavedJobSerializer,
    JobStatisticsSerializer,
    CompanyStatisticsSerializer,
)
from jobs.filters import JobFilter
from jobs.permissions import (
    IsCompanyOrReadOnly,
    IsJobOwner,
    IsJobCreator,
    CanViewJob,
    IsApplicationOwnerOrJobCompany,
    IsApplicant,
    IsCompany,
    IsSavedJobOwner,
)
from users.choices import JobStatus, ApplicationStatus, Role
from users.models import User, ApplicantProfile, CompanyProfile
from users.utils import CustomPagination


# --- Job Views ---
class JobListView(APIView):
    """API to get list of jobs"""

    permission_classes = [AllowAny]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = JobFilter
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-created_at"]

    def get(self, request):
        # Lấy danh sách job với các quan hệ cần thiết
        queryset = (
            Job.objects.select_related("company")
            .prefetch_related(
                "locations",
                "industries",
                "skills",
                "saved_by",
            )
            .all()
        )

        # Lấy status từ query params nếu có
        status_filter = request.query_params.get("status")

        # Nếu có filter theo status cụ thể, ưu tiên áp dụng filter này trước
        if status_filter and status_filter in dict(JobStatus.choices):
            queryset = queryset.filter(status=status_filter)

            # Nếu filter là DRAFT, chỉ cho phép công ty xem job DRAFT của chính họ
            if status_filter == JobStatus.DRAFT:
                if (
                    not request.user.is_authenticated
                    or request.user.role != Role.COMPANY
                ):
                    return Response(
                        {"detail": "You don't have permission to view draft jobs"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                # Nếu là công ty, chỉ xem được job DRAFT của chính họ
                company = request.user.company_profile
                if company:
                    queryset = queryset.filter(company=company)
                else:
                    return Response(
                        {"detail": "You need to complete your company profile"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        else:
            # Nếu không có filter status cụ thể, áp dụng quy tắc mặc định
            # Applicant không thể xem job DRAFT
            if not request.user.is_authenticated or request.user.role == Role.APPLICANT:
                queryset = queryset.exclude(status=JobStatus.DRAFT)

            # Nếu là công ty, chỉ hiển thị job của họ và job PUBLISHED của công ty khác
            elif request.user.role == Role.COMPANY:
                company = request.user.company_profile
                if company:
                    # Job của công ty hiện tại + các job PUBLISHED của công ty khác
                    queryset = queryset.filter(
                        Q(company=company)
                        | ~Q(company=company) & ~Q(status=JobStatus.DRAFT)
                    )
                else:
                    # Nếu công ty chưa có profile, chỉ xem job PUBLISHED
                    queryset = queryset.exclude(status=JobStatus.DRAFT)

        # Tìm kiếm
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(requirements__icontains=search)
                | Q(company__name__icontains=search)
                | Q(city__icontains=search)
            )

        # Filter các trường khác
        filterset = JobFilter(request.query_params, queryset=queryset)
        if filterset.is_valid():
            queryset = filterset.qs

        # Áp dụng ordering
        ordering = request.query_params.get("ordering", "-created_at")
        if ordering:
            queryset = queryset.order_by(ordering)

        print("Query params:", request.query_params)

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
        job = get_object_or_404(Job.objects.select_related("company"), id=pk)

        # Kiểm tra quyền xem job
        self.check_object_permissions(request, job)

        # Ghi lại lượt xem nếu có JobStatistics
        job_stats, created = JobStatistics.objects.get_or_create(job=job)
        job_stats.view_count += 1
        job_stats.save()

        # Trả về thông tin job
        serializer = JobSerializer(job, context={"request": request})
        return Response(serializer.data)


class JobCreateView(APIView):
    """API to create a new job"""

    permission_classes = [IsAuthenticated, IsCompany]

    def post(self, request):
        serializer = JobSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            # Gán company profile
            user = request.user
            company_profile = user.company_profile
            if not company_profile:
                return Response(
                    {
                        "detail": "You need to complete your company profile before creating a job"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Tạo job
            job = serializer.save()

            # Cập nhật thống kê công ty
            company_stats, created = CompanyStatistics.objects.get_or_create(
                company=company_profile
            )
            company_stats.total_jobs += 1
            if job.status == JobStatus.PUBLISHED:
                company_stats.active_jobs += 1
            company_stats.save()

            # Trả về thông tin job
            serializer = JobSerializer(job, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # Xử lý lỗi
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobUpdateView(APIView):
    """API to update a job"""

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
                {"detail": "Cannot update a closed job"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Lưu trạng thái trước đó của job
        was_published = job.status == JobStatus.PUBLISHED

        # Cập nhật job
        serializer = JobSerializer(job, data=request.data, context={"request": request})
        if serializer.is_valid():
            updated_job = serializer.save()

            # Cập nhật trạng thái theo yêu cầu từ client
            # Nếu status được chỉ định trong request, sử dụng nó
            # Nếu không được chỉ định và job đã published trước đó, giữ nguyên trạng thái published
            if "status" in request.data:
                # Trạng thái đã được xử lý trong serializer.save()
                pass
            elif was_published:
                # Giữ nguyên trạng thái PUBLISHED thay vì chuyển về DRAFT
                updated_job.status = JobStatus.PUBLISHED
                updated_job.save(update_fields=["status"])

            # Cập nhật thống kê công ty nếu trạng thái thay đổi
            if updated_job.status != job.status:
                company_stats, created = CompanyStatistics.objects.get_or_create(
                    company=job.company
                )
                if updated_job.status == JobStatus.PUBLISHED:
                    company_stats.active_jobs += 1
                elif job.status == JobStatus.PUBLISHED:
                    company_stats.active_jobs = max(0, company_stats.active_jobs - 1)
                company_stats.save()

            serializer = JobSerializer(updated_job, context={"request": request})
            return Response(serializer.data)

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

        # Lưu trạng thái hiện tại để kiểm tra thay đổi
        old_status = job.status

        # Cập nhật job
        serializer = JobSerializer(
            job, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            updated_job = serializer.save()

            # Kiểm tra nếu trạng thái đã thay đổi
            if updated_job.status != old_status:
                # Cập nhật thống kê công ty
                company_stats, created = CompanyStatistics.objects.get_or_create(
                    company=job.company
                )
                if updated_job.status == JobStatus.PUBLISHED:
                    company_stats.active_jobs += 1
                elif old_status == JobStatus.PUBLISHED:
                    company_stats.active_jobs = max(0, company_stats.active_jobs - 1)
                company_stats.save()

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
        job = get_object_or_404(Job.objects.select_related("company"), id=pk)
        self.check_object_permissions(request, job)

        # Kiểm tra xem job có applications không
        if job.applications.exists():
            return Response(
                {
                    "detail": "Cannot delete a job that has applications. Close it instead."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Xóa job
        with transaction.atomic():
            # Cập nhật thống kê công ty
            company_stats, created = CompanyStatistics.objects.get_or_create(
                company=job.company
            )
            company_stats.total_jobs = max(0, company_stats.total_jobs - 1)
            if job.status == JobStatus.PUBLISHED:
                company_stats.active_jobs = max(0, company_stats.active_jobs - 1)
            company_stats.save()

            # Xóa job
            job.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class JobStatusUpdateView(APIView):
    """API to update job status"""

    permission_classes = [IsAuthenticated, IsJobCreator]

    def patch(self, request, pk):
        # Lấy thông tin job với các quan hệ cần thiết
        job = get_object_or_404(Job.objects.select_related("company"), id=pk)
        self.check_object_permissions(request, job)

        # Lấy trạng thái cũ để so sánh
        old_status = job.status

        # Lấy trạng thái mới từ request
        status_value = request.data.get("status")
        if not status_value:
            return Response(
                {"detail": "Status is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Kiểm tra giá trị status hợp lệ
        valid_statuses = [s[0] for s in JobStatus.choices]
        if status_value not in valid_statuses:
            return Response(
                {"detail": f"Invalid status. Must be one of {valid_statuses}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra nếu job đã đóng
        if job.status == JobStatus.CLOSED:
            return Response(
                {"detail": "Cannot update status of a closed job"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra chuyển trạng thái hợp lệ
        if status_value == JobStatus.PUBLISHED:
            # Kiểm tra các trường bắt buộc khi publish
            required_fields = ["title", "description", "job_type", "experience_level"]
            missing_fields = [
                field for field in required_fields if not getattr(job, field)
            ]
            if missing_fields:
                return Response(
                    {
                        "detail": f"Cannot publish job. Missing required fields: {', '.join(missing_fields)}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Cập nhật trạng thái
        with transaction.atomic():
            job.status = status_value
            # Nếu chuyển sang CLOSED, set closed_date
            if status_value == JobStatus.CLOSED:
                job.closed_date = timezone.now().date()

                # Từ chối các đơn ứng tuyển chưa xử lý
                pending_applications = job.job_applications.filter(
                    status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING]
                )
                pending_applications.update(
                    status=ApplicationStatus.REJECTED,
                    note="Job has been closed by the company",
                )

            job.save()

            # Cập nhật thống kê công ty
            company_stats, created = CompanyStatistics.objects.get_or_create(
                company=job.company
            )
            if (
                status_value == JobStatus.PUBLISHED
                and old_status != JobStatus.PUBLISHED
            ):
                company_stats.active_jobs += 1
            elif (
                old_status == JobStatus.PUBLISHED
                and status_value != JobStatus.PUBLISHED
            ):
                company_stats.active_jobs = max(0, company_stats.active_jobs - 1)
            company_stats.save()

        # Trả về thông tin job
        serializer = JobSerializer(job, context={"request": request})
        return Response(serializer.data)


class AutoCloseJobsView(APIView):
    """API to automatically close expired jobs"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Only admin has permission to call this API
        if request.user.role != Role.ADMIN:
            return Response(
                {"detail": "Only admin can perform this action"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get today's date
        today = timezone.now().date()

        # Find jobs that should be closed
        jobs_to_close = Job.objects.filter(
            status=JobStatus.PUBLISHED, closed_date__lt=today
        )

        # Number of jobs to close
        jobs_count = jobs_to_close.count()

        if jobs_count == 0:
            return Response({"detail": "No jobs to close"})

        # Close jobs and reject pending applications
        with transaction.atomic():
            # Get list of job IDs for updating company statistics later
            job_ids = list(jobs_to_close.values_list("id", flatten=True))
            company_ids = list(jobs_to_close.values_list("company_id", flatten=True))

            # Update job status
            jobs_to_close.update(status=JobStatus.CLOSED)

            # Find pending applications for closed jobs
            pending_applications = JobApplication.objects.filter(
                job_id__in=job_ids,
                status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING],
            )

            # Reject pending applications
            pending_applications.update(
                status=ApplicationStatus.REJECTED,
                note="Job has been automatically closed due to expired closing date",
            )

            # Update company statistics
            for company_id in set(company_ids):
                company_stats, created = CompanyStatistics.objects.get_or_create(
                    company_id=company_id
                )
                company_stats.active_jobs = max(0, company_stats.active_jobs - 1)
                company_stats.save()

        return Response(
            {
                "detail": f"Successfully closed {jobs_count} jobs and rejected {pending_applications.count()} pending applications"
            }
        )


class JobSaveView(APIView):
    """API to save/unsave a job"""

    permission_classes = [IsAuthenticated, IsApplicant]

    def post(self, request, pk):
        # Kiểm tra job tồn tại
        job = get_object_or_404(Job, id=pk)

        # Chỉ có thể lưu job PUBLISHED
        if job.status != JobStatus.PUBLISHED:
            return Response(
                {"detail": "Cannot save a job that is not published"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra job đã được lưu chưa
        applicant = request.user.applicant_profile
        saved_job = SavedJob.objects.filter(applicant=applicant, job=job).first()

        if saved_job:
            return Response(
                {"detail": "Job already saved"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Lưu job
        saved_job = SavedJob.objects.create(applicant=applicant, job=job)
        serializer = SavedJobSerializer(saved_job)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        # Kiểm tra job tồn tại
        job = get_object_or_404(Job, id=pk)

        # Tìm và xóa saved job trực tiếp
        applicant = request.user.applicant_profile
        result = SavedJob.objects.filter(applicant=applicant, job=job).delete()

        # Nếu không có bản ghi nào bị xóa
        if result[0] == 0:
            return Response(
                {"detail": "Job not saved"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Trả về phản hồi ngay lập tức
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobStatisticsView(APIView):
    """API to get statistics about a job"""

    permission_classes = [IsAuthenticated, IsJobOwner]

    def get(self, request, pk):
        # Kiểm tra job tồn tại và quyền xem
        job = get_object_or_404(Job, id=pk)
        self.check_object_permissions(request, job)

        # Lấy thống kê job
        job_stats, created = JobStatistics.objects.get_or_create(job=job)

        # Cập nhật thống kê nếu cần
        if created or job_stats.application_count != job.job_applications.count():
            job_stats.application_count = job.job_applications.count()
            job_stats.accepted_count = job.job_applications.filter(
                status=ApplicationStatus.ACCEPTED
            ).count()
            job_stats.rejected_count = job.job_applications.filter(
                status=ApplicationStatus.REJECTED
            ).count()

        # Serialize và trả về kết quả
        serializer = JobStatisticsSerializer(job_stats)
        return Response(serializer.data)


class CompanyJobsView(APIView):
    """API to get all jobs for a specific company with optional status filtering"""

    permission_classes = [AllowAny]
    pagination_class = CustomPagination

    def get(self, request, company_id):
        # Kiểm tra company tồn tại
        company = get_object_or_404(CompanyProfile, user_id=company_id)

        # Lấy status filter từ query params (all, published, draft, closed)
        status_filter = request.query_params.get("status", "all").lower()

        # Lấy danh sách job của company
        queryset = Job.objects.filter(company=company)

        # Áp dụng filter theo status nếu có
        if status_filter != "all":
            if status_filter in dict(JobStatus.choices):
                queryset = queryset.filter(status=status_filter)
            else:
                return Response(
                    {
                        "detail": f"Invalid status filter. Must be one of: all, {', '.join(JobStatus.get_values())}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Kiểm tra quyền xem
        # Nếu không phải company sở hữu, chỉ hiển thị job PUBLISHED
        if (
            not request.user.is_authenticated
            or request.user.role != Role.COMPANY
            or request.user.company_profile != company
        ):
            queryset = queryset.filter(status=JobStatus.PUBLISHED)

        # Sắp xếp theo thời gian tạo mới nhất
        queryset = queryset.order_by("-created_at")

        # Phân trang
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize và trả về kết quả
        serializer = JobSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)


class CompanyJobsCountView(APIView):
    """API to get count of jobs by status for a specific company"""

    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        # Kiểm tra company tồn tại
        company = get_object_or_404(CompanyProfile, user_id=company_id)

        # Kiểm tra quyền xem
        if request.user.role != Role.ADMIN and (
            request.user.role != Role.COMPANY or request.user.company_profile != company
        ):
            return Response(
                {"detail": "You do not have permission to view these statistics"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Đếm số lượng job theo từng trạng thái
        total_count = Job.objects.filter(company=company).count()
        published_count = Job.objects.filter(
            company=company, status=JobStatus.PUBLISHED
        ).count()
        draft_count = Job.objects.filter(
            company=company, status=JobStatus.DRAFT
        ).count()
        closed_count = Job.objects.filter(
            company=company, status=JobStatus.CLOSED
        ).count()

        # Trả về kết quả
        return Response(
            {
                "all": total_count,
                "published": published_count,
                "draft": draft_count,
                "closed": closed_count,
            }
        )


class CompanyStatisticsView(APIView):
    """API to get statistics about a company"""

    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        # Kiểm tra company tồn tại
        company = get_object_or_404(CompanyProfile, user_id=company_id)

        # Kiểm tra quyền xem
        if request.user.role != Role.ADMIN and (
            request.user.role != Role.COMPANY or request.user.company_profile != company
        ):
            return Response(
                {"detail": "You do not have permission to view these statistics"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy hoặc tạo thống kê công ty
        company_stats, created = CompanyStatistics.objects.get_or_create(
            company=company
        )

        # Cập nhật thống kê nếu cần
        if created:
            with transaction.atomic():
                # Tính toán các số liệu thống kê
                total_jobs = Job.objects.filter(company=company).count()
                active_jobs = Job.objects.filter(
                    company=company, status=JobStatus.PUBLISHED
                ).count()

                # Tổng số đơn ứng tuyển
                job_ids = Job.objects.filter(company=company).values_list(
                    "id", flat=True
                )
                total_applications = JobApplication.objects.filter(
                    job_id__in=job_ids
                ).count()

                # Số lượng ứng viên được nhận
                hired_applicants = JobApplication.objects.filter(
                    job_id__in=job_ids, status=ApplicationStatus.ACCEPTED
                ).count()

                # Tỷ lệ tuyển dụng thành công
                average_hire_rate = (
                    hired_applicants / total_applications
                    if total_applications > 0
                    else 0
                )

                # Cập nhật thống kê
                company_stats.total_jobs = total_jobs
                company_stats.active_jobs = active_jobs
                company_stats.total_applications = total_applications
                company_stats.hired_applicants = hired_applicants
                company_stats.average_hire_rate = average_hire_rate
                company_stats.save()

        # Serialize và trả về kết quả
        serializer = CompanyStatisticsSerializer(company_stats)
        return Response(serializer.data)


class SavedJobListView(APIView):
    """API to get list of saved jobs"""

    permission_classes = [IsAuthenticated, IsApplicant]
    pagination_class = CustomPagination

    def get(self, request):
        # Lấy danh sách saved jobs của applicant hiện tại
        applicant = request.user.applicant_profile
        queryset = SavedJob.objects.filter(applicant=applicant).select_related(
            "job", "job__company"
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
        if request.user.role != Role.ADMIN and (
            request.user.role != Role.APPLICANT
            or str(request.user.id) != str(applicant_id)
        ):
            return Response(
                {"detail": "You do not have permission to view these saved jobs"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy danh sách saved jobs của applicant
        applicant = get_object_or_404(ApplicantProfile, user_id=applicant_id)
        queryset = SavedJob.objects.filter(applicant=applicant).select_related(
            "job", "job__company"
        )

        # Phân trang
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize và trả về kết quả
        serializer = SavedJobSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)
