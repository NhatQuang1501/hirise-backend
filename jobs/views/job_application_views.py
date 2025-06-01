from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from jobs.models import Job, JobApplication, InterviewSchedule, CVReview
from jobs.serializers import (
    JobApplicationSerializer,
    InterviewScheduleSerializer,
    CVReviewSerializer,
)
from jobs.permissions import (
    IsApplicationOwnerOrJobCompany,
    IsApplicant,
    IsCompany,
)
from users.choices import ApplicationStatus, JobStatus, Role
from users.models import ApplicantProfile
from users.utils import CustomPagination


class JobApplicationListView(APIView):
    """API to get list of job applications"""

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request):
        user = request.user

        # Nếu là ứng viên, chỉ lấy đơn của họ
        if user.role == Role.APPLICANT:
            queryset = (
                JobApplication.objects.filter(applicant=user.applicant_profile)
                .select_related("job", "job__company")
                .order_by("-created_at")
            )

        # Nếu là công ty, lấy đơn cho job của họ
        elif user.role == Role.COMPANY:
            company = user.company_profile
            if not company:
                return Response(
                    {"detail": "You haven't completed your company profile yet"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = (
                JobApplication.objects.filter(job__company=company)
                .select_related("job", "applicant", "applicant__user")
                .order_by("-created_at")
            )

        # Nếu là admin, lấy tất cả đơn
        elif user.role == Role.ADMIN:
            queryset = (
                JobApplication.objects.all()
                .select_related("job", "job__company", "applicant", "applicant__user")
                .order_by("-created_at")
            )

        else:
            return Response(
                {"detail": "You don't have permission to view the application list"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lọc theo job nếu có
        job_id = request.query_params.get("job_id")
        if job_id:
            queryset = queryset.filter(job_id=job_id)

        # Lọc theo applicant nếu có
        applicant_id = request.query_params.get("applicant_id")
        if applicant_id:
            queryset = queryset.filter(applicant_id=applicant_id)

        # Lọc theo trạng thái nếu có
        status_filter = request.query_params.get("status")
        if status_filter:
            if status_filter in dict(ApplicationStatus.choices):
                queryset = queryset.filter(status=status_filter)

        # Phân trang
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize và trả về kết quả
        serializer = JobApplicationSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)


class JobApplicationDetailView(APIView):
    """API to view the details of an application"""

    permission_classes = [IsAuthenticated, IsApplicationOwnerOrJobCompany]

    def get(self, request, pk):
        # Lấy đơn ứng tuyển
        application = get_object_or_404(
            JobApplication.objects.select_related(
                "job", "job__company", "applicant", "applicant__user"
            ),
            id=pk,
        )

        # Kiểm tra quyền xem
        self.check_object_permissions(request, application)

        # Serialize và trả về kết quả
        serializer = JobApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)


class JobApplicationCreateView(APIView):
    """API to create a new job application"""

    permission_classes = [IsAuthenticated, IsApplicant]

    def post(self, request, job_id):
        # Lấy thông tin job
        job = get_object_or_404(Job, id=job_id)

        # Kiểm tra job có ở trạng thái published không
        if job.status != JobStatus.PUBLISHED:
            return Response(
                {"detail": "Cannot apply for a job that is not in published status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra ứng viên đã ứng tuyển job này chưa
        applicant_profile = request.user.applicant_profile
        if JobApplication.objects.filter(applicant=applicant_profile, job=job).exists():
            return Response(
                {"detail": "You have already applied for this job"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Tạo context với job
        context = {"request": request, "job": job}

        # Tạo đơn ứng tuyển
        serializer = JobApplicationSerializer(data=request.data, context=context)
        if serializer.is_valid():
            application = serializer.save()

            # Cập nhật thống kê job
            job_stats = job.statistics
            job_stats.application_count += 1
            job_stats.save()

            # Cập nhật thống kê công ty
            company_stats = job.company.statistics
            company_stats.total_applications += 1
            company_stats.save()

            # Trả về thông tin đơn ứng tuyển
            serializer = JobApplicationSerializer(
                application, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # Xử lý lỗi
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobApplicationUpdateStatusView(APIView):
    """API to update the status of a job application"""

    permission_classes = [IsAuthenticated, IsCompany]

    def patch(self, request, pk):
        # Lấy đơn ứng tuyển
        application = get_object_or_404(JobApplication, id=pk)

        # Kiểm tra công ty có sở hữu job này không
        company = request.user.company_profile
        if not company or application.job.company != company:
            return Response(
                {"detail": "You don't have permission to update this application"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Kiểm tra trạng thái mới hợp lệ
        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"detail": "New status is not provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status not in dict(ApplicationStatus.choices):
            return Response(
                {"detail": f"Status '{new_status}' is not valid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra trạng thái hiện tại
        old_status = application.status
        if old_status == new_status:
            return Response(
                {"detail": f"Application is already in {new_status} status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra nếu đơn đã bị từ chối hoặc chấp nhận thì không thể thay đổi
        if old_status in [
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
        ]:
            return Response(
                {
                    "detail": f"Cannot change the status of an application that is {application.get_status_display().lower()}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cập nhật trạng thái
        application.status = new_status

        # Cập nhật note nếu có
        note = request.data.get("note")
        if note:
            application.note = note

        application.save()

        # Cập nhật thống kê job và công ty nếu là ACCEPTED hoặc REJECTED
        if new_status == ApplicationStatus.ACCEPTED:
            job_stats = application.job.statistics
            job_stats.accepted_count += 1
            job_stats.save()

            company_stats = application.job.company.statistics
            company_stats.hired_applicants += 1
            # Cập nhật tỉ lệ tuyển dụng thành công
            company_stats.average_hire_rate = (
                company_stats.hired_applicants / company_stats.total_applications
                if company_stats.total_applications > 0
                else 0
            )
            company_stats.save()

        elif new_status == ApplicationStatus.REJECTED:
            job_stats = application.job.statistics
            job_stats.rejected_count += 1
            job_stats.save()

        # Trả về thông tin đơn ứng tuyển sau khi cập nhật
        serializer = JobApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)


class JobApplicationsForJobView(APIView):
    """API to get list of applications for a specific job"""

    permission_classes = [IsAuthenticated, IsCompany]
    pagination_class = CustomPagination

    def get(self, request, job_id):
        # Lấy thông tin job
        job = get_object_or_404(Job, id=job_id)

        # Kiểm tra quyền xem - chỉ công ty sở hữu job mới được xem
        company = request.user.company_profile
        if not company or job.company != company:
            return Response(
                {
                    "detail": "You don't have permission to view applications for this job"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy danh sách đơn ứng tuyển
        queryset = (
            JobApplication.objects.filter(job=job)
            .select_related("applicant", "applicant__user")
            .order_by("-created_at")
        )

        # Lọc theo trạng thái nếu có
        status_filter = request.query_params.get("status")
        if status_filter:
            if status_filter in dict(ApplicationStatus.choices):
                queryset = queryset.filter(status=status_filter)

        # Phân trang
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize và trả về kết quả
        serializer = JobApplicationSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)


class ApplicantApplicationsView(APIView):
    """API to get list of applications for a specific applicant"""

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, applicant_id):
        # Kiểm tra quyền xem
        if request.user.role == Role.APPLICANT and str(request.user.id) != applicant_id:
            return Response(
                {
                    "detail": "You don't have permission to view applications of other applicants"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.user.role == Role.COMPANY:
            # Công ty chỉ xem được đơn ứng tuyển vào công ty của họ
            company = request.user.company_profile
            if not company:
                return Response(
                    {"detail": "You haven't completed your company profile yet"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Lấy applicant profile
            applicant = get_object_or_404(ApplicantProfile, user_id=applicant_id)

            # Lấy đơn ứng tuyển vào công ty
            queryset = (
                JobApplication.objects.filter(applicant=applicant, job__company=company)
                .select_related("job", "job__company")
                .order_by("-created_at")
            )
        else:
            # Admin hoặc chính applicant xem đơn của mình
            applicant = get_object_or_404(ApplicantProfile, user_id=applicant_id)
            queryset = (
                JobApplication.objects.filter(applicant=applicant)
                .select_related("job", "job__company")
                .order_by("-created_at")
            )

        # Lọc theo trạng thái nếu có
        status_filter = request.query_params.get("status")
        if status_filter and status_filter in dict(ApplicationStatus.choices):
            queryset = queryset.filter(status=status_filter)

        # Phân trang
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize và trả về kết quả
        serializer = JobApplicationSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)


class InterviewScheduleView(APIView):
    """API to manage interview schedule for an application"""

    permission_classes = [IsAuthenticated, IsApplicationOwnerOrJobCompany]

    def get(self, request, application_id):
        # Lấy đơn ứng tuyển
        application = get_object_or_404(JobApplication, id=application_id)

        # Kiểm tra quyền xem
        self.check_object_permissions(request, application)

        # Lấy lịch phỏng vấn nếu có
        interview = InterviewSchedule.objects.filter(application=application).first()

        if not interview:
            return Response(
                {"detail": "No interview schedule found for this application"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Serialize và trả về kết quả
        serializer = InterviewScheduleSerializer(interview)
        return Response(serializer.data)

    def post(self, request, application_id):
        # Chỉ công ty mới được tạo lịch phỏng vấn
        if request.user.role != Role.COMPANY:
            return Response(
                {"detail": "Only companies can create interview schedules"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy đơn ứng tuyển
        application = get_object_or_404(JobApplication, id=application_id)

        # Kiểm tra quyền tạo
        if application.job.company != request.user.company_profile:
            return Response(
                {
                    "detail": "You don't have permission to schedule interviews for this application"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Kiểm tra nếu đã có lịch phỏng vấn
        if InterviewSchedule.objects.filter(application=application).exists():
            return Response(
                {"detail": "Interview schedule already exists for this application"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Tạo lịch phỏng vấn
        serializer = InterviewScheduleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(application=application)

            # Cập nhật trạng thái đơn ứng tuyển nếu đang ở PENDING
            if application.status == ApplicationStatus.PENDING:
                application.status = ApplicationStatus.REVIEWING
                application.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, application_id):
        # Chỉ công ty mới được cập nhật lịch phỏng vấn
        if request.user.role != Role.COMPANY:
            return Response(
                {"detail": "Only companies can update interview schedules"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy đơn ứng tuyển
        application = get_object_or_404(JobApplication, id=application_id)

        # Kiểm tra quyền cập nhật
        if application.job.company != request.user.company_profile:
            return Response(
                {
                    "detail": "You don't have permission to update interviews for this application"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy lịch phỏng vấn
        interview = get_object_or_404(InterviewSchedule, application=application)

        # Cập nhật lịch phỏng vấn
        serializer = InterviewScheduleSerializer(interview, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CVReviewView(APIView):
    """API to manage CV reviews for an application"""

    permission_classes = [IsAuthenticated, IsApplicationOwnerOrJobCompany]

    def get(self, request, application_id):
        # Lấy đơn ứng tuyển
        application = get_object_or_404(JobApplication, id=application_id)

        # Kiểm tra quyền xem
        self.check_object_permissions(request, application)

        # Lấy đánh giá CV nếu có
        cv_review = CVReview.objects.filter(application=application).first()

        if not cv_review:
            return Response(
                {"detail": "No CV review found for this application"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Serialize và trả về kết quả
        serializer = CVReviewSerializer(cv_review)
        return Response(serializer.data)

    def post(self, request, application_id):
        # Chỉ công ty mới được tạo đánh giá CV
        if request.user.role != Role.COMPANY:
            return Response(
                {"detail": "Only companies can create CV reviews"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy đơn ứng tuyển
        application = get_object_or_404(JobApplication, id=application_id)

        # Kiểm tra quyền tạo
        if application.job.company != request.user.company_profile:
            return Response(
                {
                    "detail": "You don't have permission to review CVs for this application"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Kiểm tra nếu đã có đánh giá CV
        if CVReview.objects.filter(application=application).exists():
            return Response(
                {"detail": "CV review already exists for this application"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Tạo đánh giá CV
        serializer = CVReviewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(application=application)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, application_id):
        # Chỉ công ty mới được cập nhật đánh giá CV
        if request.user.role != Role.COMPANY:
            return Response(
                {"detail": "Only companies can update CV reviews"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy đơn ứng tuyển
        application = get_object_or_404(JobApplication, id=application_id)

        # Kiểm tra quyền cập nhật
        if application.job.company != request.user.company_profile:
            return Response(
                {
                    "detail": "You don't have permission to update CV reviews for this application"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy đánh giá CV
        cv_review = get_object_or_404(CVReview, application=application)

        # Cập nhật đánh giá CV
        serializer = CVReviewSerializer(cv_review, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
