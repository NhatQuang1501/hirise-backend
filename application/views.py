from django.shortcuts import get_object_or_404
from rest_framework import status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .models import JobApplication, CVAnalysis, InterviewSchedule, TestFileUpload
from .serializers import (
    JobApplicationSerializer,
    CVAnalysisSerializer,
    JobApplicationListSerializer,
    InterviewScheduleSerializer,
    TestFileUploadSerializer,
)
from jobs.models import Job
from users.models import ApplicantProfile
from users.choices import ApplicationStatus, Role
from .permissions import IsApplicantOwner, IsCompanyOwner
from .filters import JobApplicationFilter
from AI.cv_processing import process_cv_on_application
from AI.matching_service import MatchingService
from users.utils import CustomPagination


class JobApplicationListCreateView(APIView):
    """
    API endpoint để liệt kê và tạo mới đơn ứng tuyển
    """

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, format=None):
        user = request.user

        # Lọc dữ liệu theo vai trò người dùng
        if user.role == Role.APPLICANT:
            try:
                applicant = ApplicantProfile.objects.get(user=user)
                # Ứng viên chỉ thấy đơn ứng tuyển của mình
                queryset = JobApplication.objects.filter(
                    applicant=applicant
                ).select_related("applicant__user", "job__company")
            except ApplicantProfile.DoesNotExist:
                return Response(
                    {"detail": "Applicant profile not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        elif user.role == Role.COMPANY:
            try:
                company = user.company_profile
                # Công ty chỉ thấy đơn ứng tuyển cho công việc của mình
                queryset = (
                    JobApplication.objects.filter(job__company=company)
                    .select_related("applicant__user", "job__company")
                    .prefetch_related("cv_analysis")
                )
            except:
                return Response(
                    {"detail": "Company profile not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        elif user.role == Role.ADMIN:
            # Admin thấy tất cả
            queryset = (
                JobApplication.objects.all()
                .select_related("applicant__user", "job__company")
                .prefetch_related("cv_analysis")
            )
        else:
            return Response(
                {"detail": "You don't have permission to view applications."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Áp dụng bộ lọc
        filter_backend = JobApplicationFilter(request.query_params, queryset=queryset)
        queryset = filter_backend.qs

        # Áp dụng sắp xếp
        ordering = request.query_params.get("ordering", "-created_at")
        if ordering:
            if ordering.startswith("-"):
                field = ordering[1:]
                queryset = queryset.order_by(f"-{field}")
            else:
                queryset = queryset.order_by(ordering)

        # Áp dụng phân trang
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        # Chọn serializer phù hợp
        if user.role == Role.COMPANY:
            serializer = JobApplicationListSerializer(
                page, many=True, context={"request": request}
            )
        else:
            serializer = JobApplicationSerializer(
                page, many=True, context={"request": request}
            )

        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        # Kiểm tra người dùng có phải là ứng viên không
        if request.user.role != Role.APPLICANT:
            return Response(
                {"detail": "Only applicants can apply for jobs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy thông tin ứng viên từ user hiện tại
        try:
            applicant = ApplicantProfile.objects.get(user=request.user)
        except ApplicantProfile.DoesNotExist:
            return Response(
                {"detail": "Applicant profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra job có tồn tại không
        job_id = request.data.get("job_id")
        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            return Response(
                {"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Thêm applicant vào data
        data = request.data.copy()
        data["applicant"] = applicant.id
        data["job"] = job.id

        serializer = JobApplicationSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobApplicationDetailView(APIView):
    """
    API endpoint để xem chi tiết, cập nhật và xóa đơn ứng tuyển
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        user = self.request.user

        try:
            application = JobApplication.objects.select_related(
                "applicant__user", "job__company"
            ).get(pk=pk)

            # Kiểm tra quyền truy cập
            if user.role == Role.APPLICANT and application.applicant.user != user:
                # Ứng viên chỉ xem được đơn của mình
                raise JobApplication.DoesNotExist

            if user.role == Role.COMPANY and application.job.company.user != user:
                # Công ty chỉ xem được đơn cho công việc của mình
                raise JobApplication.DoesNotExist

            return application
        except JobApplication.DoesNotExist:
            return None

    def get(self, request, pk, format=None):
        application = self.get_object(pk)
        if not application:
            return Response(
                {"detail": "Application not found or you don't have permission."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = JobApplicationSerializer(application, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk, format=None):
        application = self.get_object(pk)
        if not application:
            return Response(
                {"detail": "Application not found or you don't have permission."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Chỉ cho phép ứng viên xóa đơn của mình
        if (
            request.user.role != Role.APPLICANT
            or application.applicant.user != request.user
        ):
            return Response(
                {"detail": "Only applicants can withdraw their own applications."},
                status=status.HTTP_403_FORBIDDEN,
            )

        application.delete()
        return Response(
            {"success": True, "message": "Application withdrawn successfully."},
            status=status.HTTP_200_OK,
        )


class JobApplicationAnalyzeView(APIView):
    """
    API endpoint để phân tích CV
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        user = self.request.user

        try:
            application = JobApplication.objects.select_related("job__company").get(
                pk=pk
            )

            # Kiểm tra quyền truy cập (chỉ công ty sở hữu job mới có quyền phân tích)
            if user.role != Role.COMPANY or application.job.company.user != user:
                raise JobApplication.DoesNotExist

            return application
        except JobApplication.DoesNotExist:
            return None

    def post(self, request, pk, format=None):
        application = self.get_object(pk)
        if not application:
            return Response(
                {"detail": "Application not found or you don't have permission."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Cập nhật trạng thái đang xử lý
        application.status = ApplicationStatus.PROCESSING
        application.save()

        try:
            # Xử lý CV và lưu dữ liệu
            processed_data = process_cv_on_application(application)

            # Phân tích mức độ phù hợp
            matching_service = MatchingService()
            match_result = matching_service.match_job_cv(
                application.job.id, application_id=application.id
            )
            match_score = match_result.match_score if match_result else 0

            # Lưu kết quả phân tích
            cv_analysis, created = CVAnalysis.objects.update_or_create(
                application=application,
                defaults={
                    "extracted_content": processed_data.combined_text,
                    "match_score": match_score,
                },
            )

            # Cập nhật trạng thái đã xem xét
            application.status = ApplicationStatus.REVIEWING
            application.save()

            return Response(
                {
                    "success": True,
                    "match_score": match_score,
                    "message": "CV analysis completed successfully.",
                }
            )

        except Exception as e:
            # Nếu có lỗi, đặt lại trạng thái
            application.status = ApplicationStatus.PENDING
            application.save()

            return Response(
                {"success": False, "message": f"Failed to analyze CV: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class JobApplicationStatusView(APIView):
    """
    API endpoint để thay đổi trạng thái đơn ứng tuyển
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        user = self.request.user

        try:
            application = JobApplication.objects.select_related(
                "applicant__user", "job__company"
            ).get(pk=pk)

            return application
        except JobApplication.DoesNotExist:
            return None

    def post(self, request, pk, action, format=None):
        application = self.get_object(pk)
        if not application:
            return Response(
                {"detail": "Application not found."}, status=status.HTTP_404_NOT_FOUND
            )

        user = request.user

        if action == "accept":
            # Kiểm tra quyền (chỉ công ty mới có thể chấp nhận)
            if user.role != Role.COMPANY or application.job.company.user != user:
                return Response(
                    {"detail": "Only companies can accept applications."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            application.status = ApplicationStatus.ACCEPTED
            application.save()

            return Response(
                {
                    "success": True,
                    "message": "Application accepted successfully.",
                },
                status=status.HTTP_200_OK,
            )

        elif action == "reject":
            # Kiểm tra quyền (chỉ công ty mới có thể từ chối)
            if user.role != Role.COMPANY or application.job.company.user != user:
                return Response(
                    {"detail": "Only companies can reject applications."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            application.status = ApplicationStatus.REJECTED
            application.save()

            return Response(
                {"success": True, "message": "Application rejected successfully."},
                status=status.HTTP_200_OK,
            )

        elif action == "withdraw":
            # Kiểm tra quyền (chỉ ứng viên mới có thể rút đơn)
            if user.role != Role.APPLICANT or application.applicant.user != user:
                return Response(
                    {"detail": "Only applicants can withdraw their own applications."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Xóa application thay vì chuyển trạng thái
            application.delete()

            return Response(
                {"success": True, "message": "Application withdrawn successfully."},
                status=status.HTTP_200_OK,
            )

        else:
            return Response(
                {"detail": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST
            )


class CVAnalysisListView(APIView):
    """
    API endpoint để liệt kê kết quả phân tích CV
    """

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, format=None):
        user = request.user

        # Lọc dữ liệu theo vai trò người dùng
        if user.role == Role.APPLICANT:
            try:
                applicant = ApplicantProfile.objects.get(user=user)
                # Ứng viên chỉ thấy phân tích CV của mình
                queryset = CVAnalysis.objects.filter(
                    application__applicant=applicant
                ).select_related(
                    "application__applicant__user", "application__job__company"
                )
            except ApplicantProfile.DoesNotExist:
                return Response(
                    {"detail": "Applicant profile not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        elif user.role == Role.COMPANY:
            try:
                company = user.company_profile
                # Công ty chỉ thấy phân tích CV cho công việc của mình
                queryset = CVAnalysis.objects.filter(
                    application__job__company=company
                ).select_related(
                    "application__applicant__user", "application__job__company"
                )
            except:
                return Response(
                    {"detail": "Company profile not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        elif user.role == Role.ADMIN:
            # Admin thấy tất cả
            queryset = CVAnalysis.objects.all().select_related(
                "application__applicant__user", "application__job__company"
            )
        else:
            return Response(
                {"detail": "You don't have permission to view CV analyses."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Áp dụng phân trang
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        serializer = CVAnalysisSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class CVAnalysisDetailView(APIView):
    """
    API endpoint để xem chi tiết kết quả phân tích CV
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        user = self.request.user

        try:
            cv_analysis = CVAnalysis.objects.select_related(
                "application__applicant__user", "application__job__company"
            ).get(pk=pk)

            # Kiểm tra quyền truy cập
            if (
                user.role == Role.APPLICANT
                and cv_analysis.application.applicant.user != user
            ):
                raise CVAnalysis.DoesNotExist

            if (
                user.role == Role.COMPANY
                and cv_analysis.application.job.company.user != user
            ):
                raise CVAnalysis.DoesNotExist

            return cv_analysis
        except CVAnalysis.DoesNotExist:
            return None

    def get(self, request, pk, format=None):
        cv_analysis = self.get_object(pk)
        if not cv_analysis:
            return Response(
                {"detail": "CV analysis not found or you don't have permission."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CVAnalysisSerializer(cv_analysis, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class TestFileUploadView(APIView):
    """
    API endpoint để test upload file lên storage
    """

    permission_classes = [AllowAny]

    def get(self, request, format=None):
        """
        Lấy danh sách các file đã upload
        """
        files = TestFileUpload.objects.all().order_by("-uploaded_at")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(files, request)

        serializer = TestFileUploadSerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        """
        Upload file mới
        """
        serializer = TestFileUploadSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TestFileUploadDetailView(APIView):
    """
    API endpoint để xem chi tiết, cập nhật và xóa file test
    """

    permission_classes = [AllowAny]

    def get_object(self, pk):
        try:
            return TestFileUpload.objects.get(pk=pk)
        except TestFileUpload.DoesNotExist:
            return None

    def get(self, request, pk, format=None):
        """
        Xem chi tiết file
        """
        file = self.get_object(pk)
        if not file:
            return Response(
                {"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = TestFileUploadSerializer(file, context={"request": request})
        return Response(serializer.data)

    def delete(self, request, pk, format=None):
        """
        Xóa file
        """
        file = self.get_object(pk)
        if not file:
            return Response(
                {"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND
            )

        file.delete()
        return Response(
            {"message": "File deleted successfully."}, status=status.HTTP_204_NO_CONTENT
        )
