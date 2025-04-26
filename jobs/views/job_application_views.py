from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from jobs.models import Job, JobApplication
from jobs.serializers import JobApplicationSerializer
from jobs.permissions import (
    IsApplicationOwnerOrJobRecruiter,
    IsApplicant,
    IsRecruiter,
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

        # Nếu là nhà tuyển dụng, lấy đơn cho job của công ty họ
        elif user.role == Role.RECRUITER:
            company = user.recruiter_profile.company
            if not company:
                return Response(
                    {"detail": "You haven't been assigned to any company yet"},
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

    permission_classes = [IsAuthenticated, IsApplicationOwnerOrJobRecruiter]

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

            # Trả về thông tin đơn ứng tuyển
            serializer = JobApplicationSerializer(
                application, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # Xử lý lỗi
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobApplicationUpdateStatusView(APIView):
    """API to update the status of a job application"""

    permission_classes = [IsAuthenticated, IsRecruiter]

    def patch(self, request, pk):
        # Lấy đơn ứng tuyển
        application = get_object_or_404(JobApplication, id=pk)

        # Kiểm tra recruiter có thuộc công ty của job không
        company = request.user.recruiter_profile.company
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
        if application.status == new_status:
            return Response(
                {"detail": f"Application is already in {new_status} status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra nếu đơn đã bị từ chối hoặc chấp nhận thì không thể thay đổi
        if application.status in [
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

        # Trả về thông tin đơn ứng tuyển sau khi cập nhật
        serializer = JobApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)


class JobApplicationsForJobView(APIView):
    """API to get list of applications for a specific job"""

    permission_classes = [IsAuthenticated, IsRecruiter]
    pagination_class = CustomPagination

    def get(self, request, job_id):
        # Lấy thông tin job
        job = get_object_or_404(Job, id=job_id)

        # Kiểm tra quyền xem - chỉ recruiter thuộc công ty của job mới được xem
        company = request.user.recruiter_profile.company
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

        if request.user.role == Role.RECRUITER:
            # Nhà tuyển dụng chỉ xem được đơn ứng tuyển vào công ty của họ
            company = request.user.recruiter_profile.company
            if not company:
                return Response(
                    {"detail": "You haven't been assigned to any company yet"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Lấy applicant profile
            applicant = get_object_or_404(ApplicantProfile, user_id=applicant_id)

            # Lấy đơn ứng tuyển vào công ty của nhà tuyển dụng
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
