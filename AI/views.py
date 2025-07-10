from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.http import Http404
from celery.result import AsyncResult

from application.models import JobApplication
from users.choices import ApplicationStatus
from .models import JobProcessedData, CVProcessedData, JobCVMatch
from .serializers import (
    JobProcessedDataSerializer,
    CVProcessedDataSerializer,
    CVProcessedDataDetailSerializer,
    JobCVMatchSerializer,
)
from .matching_service import MatchingService
from jobs.permissions import IsJobOwner


class JobProcessedDataListView(APIView):
    """
    API view để lấy danh sách JobProcessedData
    """

    permission_classes = [AllowAny]

    def get(self, request, format=None):
        """
        Trả về danh sách tất cả JobProcessedData
        """
        try:
            processed_data = JobProcessedData.objects.all().select_related("job")
            serializer = JobProcessedDataSerializer(processed_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Error getting JobProcessedData list: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class JobProcessedDataDetailView(APIView):
    """
    API view để lấy chi tiết một JobProcessedData
    """

    permission_classes = [AllowAny]

    def get_object(self, pk):
        """
        Lấy đối tượng JobProcessedData theo ID
        """
        try:
            return JobProcessedData.objects.select_related("job").get(pk=pk)
        except JobProcessedData.DoesNotExist:
            raise Http404("JobProcessedData not found")

    def get(self, request, pk, format=None):
        """
        Trả về chi tiết một JobProcessedData
        """
        try:
            processed_data = self.get_object(pk)
            serializer = JobProcessedDataSerializer(processed_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Http404 as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"error": f"Error getting JobProcessedData detail: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CVProcessedDataListView(APIView):
    """
    API view để lấy danh sách CVProcessedData
    """

    permission_classes = [AllowAny]

    def get(self, request, format=None):
        """
        Trả về danh sách tất cả CVProcessedData
        """
        processed_data = CVProcessedData.objects.all().select_related(
            "application__job__company", "application__applicant__user"
        )

        # Lọc theo job_id nếu có
        job_id = request.query_params.get("job_id")
        if job_id:
            processed_data = processed_data.filter(application__job__id=job_id)

        # Lọc theo applicant_id nếu có
        applicant_id = request.query_params.get("applicant_id")
        if applicant_id:
            processed_data = processed_data.filter(
                application__applicant__user__id=applicant_id
            )

        # Lọc theo company_id nếu có
        company_id = request.query_params.get("company_id")
        if company_id:
            processed_data = processed_data.filter(
                application__job__company__user__id=company_id
            )

        serializer = CVProcessedDataSerializer(processed_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CVProcessedDataDetailView(APIView):
    """
    API view để lấy chi tiết một CVProcessedData
    """

    permission_classes = [AllowAny]

    def get_object(self, pk):
        """
        Lấy đối tượng CVProcessedData theo ID
        """
        try:
            return CVProcessedData.objects.get(pk=pk)
        except CVProcessedData.DoesNotExist:
            raise Http404("CVProcessedData not found")

    def get(self, request, pk, format=None):
        """
        Trả về chi tiết một CVProcessedData
        """
        processed_data = self.get_object(pk)
        serializer = CVProcessedDataDetailSerializer(processed_data)
        return Response(serializer.data)


class CVProcessedDataByApplicationView(APIView):
    """
    API view để lấy CVProcessedData theo application_id
    """

    permission_classes = [AllowAny]

    def get(self, request, application_id, format=None):
        """
        Trả về CVProcessedData cho một application cụ thể
        """
        try:
            processed_data = CVProcessedData.objects.get(application_id=application_id)
            serializer = CVProcessedDataDetailSerializer(processed_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except CVProcessedData.DoesNotExist:
            raise Http404("CVProcessedData not found for this application")


class JobProcessedDataByJobView(APIView):
    """
    API view để lấy JobProcessedData theo job_id
    """

    permission_classes = [AllowAny]

    def get(self, request, job_id, format=None):
        """
        Trả về JobProcessedData cho một job cụ thể
        """
        try:
            processed_data = JobProcessedData.objects.select_related("job").get(
                job_id=job_id
            )
            serializer = JobProcessedDataSerializer(processed_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except JobProcessedData.DoesNotExist:
            raise Http404("JobProcessedData not found for this job")
        except Exception as e:
            return Response(
                {"error": f"Error getting JobProcessedData by job_id: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MatchJobWithCVView(APIView):
    """
    API view để đánh giá sự phù hợp giữa job và một CV cụ thể
    """

    permission_classes = [IsAuthenticated, IsJobOwner]

    def post(self, request, job_id, application_id, format=None):
        """
        Đánh giá sự phù hợp giữa job và CV
        """
        try:
            # Lấy đối tượng application
            from application.models import JobApplication
            from jobs.models import Job

            try:
                # Kiểm tra job tồn tại và thuộc về công ty hiện tại
                job = Job.objects.get(id=job_id)
                self.check_object_permissions(request, job)

                application = JobApplication.objects.get(
                    id=application_id, job_id=job_id
                )

                # Cập nhật trạng thái thành reviewing nếu đang ở trạng thái pending
                from users.choices import ApplicationStatus

                if application.status == ApplicationStatus.PENDING:
                    application.status = ApplicationStatus.REVIEWING
                    application.save()

            except JobApplication.DoesNotExist:
                return Response(
                    {"error": "Application not found"}, status=status.HTTP_404_NOT_FOUND
                )
            except Job.DoesNotExist:
                return Response(
                    {"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Kiểm tra CV đã được xử lý chưa
            try:
                cv_processed_data = CVProcessedData.objects.get(application=application)
            except CVProcessedData.DoesNotExist:
                # Nếu CV chưa được xử lý, thực hiện xử lý bất đồng bộ và trả về thông báo
                from .tasks import process_cv_task

                process_cv_task.delay(str(application_id))

                return Response(
                    {
                        "detail": "CV processing has been started. Please try again in a few moments."
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            # Thực hiện đánh giá độ phù hợp đồng bộ
            from .matching_service import MatchingService

            matching_service = MatchingService()
            match_result = matching_service.match_job_cv(
                str(job_id), application_id=str(application_id)
            )

            if match_result:
                serializer = JobCVMatchSerializer(match_result)
                return Response(
                    {
                        "detail": "Match analysis completed successfully.",
                        "match_data": serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Failed to analyze match. Please try again."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            return Response(
                {"error": f"Error evaluating match: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request, job_id, application_id, format=None):
        """
        Lấy kết quả đánh giá sự phù hợp giữa job và CV
        """
        try:
            # Kiểm tra quyền truy cập
            from jobs.models import Job

            try:
                job = Job.objects.get(id=job_id)
                self.check_object_permissions(request, job)
            except Job.DoesNotExist:
                return Response(
                    {"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Lấy kết quả đánh giá
            try:
                match = JobCVMatch.objects.get(
                    job_id=job_id, application_id=application_id
                )
                serializer = JobCVMatchSerializer(match)
                return Response(serializer.data)
            except JobCVMatch.DoesNotExist:
                return Response(
                    {
                        "detail": "Match analysis not found. You may need to run the analysis first."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

        except Exception as e:
            return Response(
                {"error": f"Error getting match results: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MatchJobWithAllCVsView(APIView):
    """
    API view để đánh giá sự phù hợp của job với tất cả CV đã apply
    """

    permission_classes = [IsAuthenticated, IsJobOwner]

    def post(self, request, job_id, format=None):
        """
        Đánh giá sự phù hợp giữa job và tất cả CV đã apply
        """
        try:
            # Kiểm tra job tồn tại và thuộc về công ty hiện tại
            from jobs.models import Job

            try:
                job = Job.objects.get(id=job_id)
                self.check_object_permissions(request, job)
            except Job.DoesNotExist:
                return Response(
                    {"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Cập nhật trạng thái của tất cả application đang ở trạng thái pending
            from application.models import JobApplication
            from users.choices import ApplicationStatus

            pending_applications = JobApplication.objects.filter(
                job_id=job_id, status=ApplicationStatus.PENDING
            )

            # Cập nhật trạng thái thành reviewing
            if pending_applications.exists():
                pending_applications.update(status=ApplicationStatus.REVIEWING)

            # Lấy danh sách các application cần đánh giá
            applications = JobApplication.objects.filter(job_id=job_id)

            if not applications.exists():
                return Response(
                    {"detail": "No applications found for this job."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Xử lý CV bất đồng bộ nếu cần
            from .tasks import process_cv_task

            applications_need_processing = []
            for application in applications:
                # Kiểm tra CV đã được xử lý chưa
                try:
                    CVProcessedData.objects.get(application=application)
                except CVProcessedData.DoesNotExist:
                    # Nếu CV chưa được xử lý, thêm vào danh sách cần xử lý
                    applications_need_processing.append(application)

            # Nếu có application cần xử lý CV, gửi task và trả về thông báo
            if applications_need_processing:
                for app in applications_need_processing:
                    process_cv_task.delay(str(app.id))

                return Response(
                    {
                        "status": "processing",
                        "detail": f"CV processing started for {len(applications_need_processing)} applications. Please try again in a few moments.",
                        "total_applications": len(applications),
                        "applications_need_processing": len(
                            applications_need_processing
                        ),
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            # Nếu tất cả CV đã được xử lý, thực hiện đánh giá đồng bộ
            from .matching_service import MatchingService

            matching_service = MatchingService()
            results = []

            for application in applications:
                # Thực hiện đánh giá độ phù hợp đồng bộ
                match_result = matching_service.match_job_cv(
                    str(job_id), application_id=str(application.id)
                )
                if match_result:
                    results.append(match_result)

            # Lấy kết quả đánh giá
            serializer = JobCVMatchSerializer(results, many=True)

            return Response(
                {
                    "status": "completed",
                    "detail": f"Match analysis completed for {len(applications)} applications.",
                    "results": serializer.data,
                    "total_applications": len(applications),
                    "processed_applications": len(results),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Error evaluating match: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GetJobMatchResultsView(APIView):
    """
    API view để lấy kết quả đánh giá sự phù hợp của job với tất cả CV
    """

    permission_classes = [IsAuthenticated, IsJobOwner]

    def get(self, request, job_id, format=None):
        """
        Lấy kết quả đánh giá sự phù hợp của job với tất cả CV
        """
        try:
            # Kiểm tra job tồn tại và thuộc về công ty hiện tại
            from jobs.models import Job

            try:
                job = Job.objects.get(id=job_id)
                self.check_object_permissions(request, job)
            except Job.DoesNotExist:
                return Response(
                    {"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND
                )

            matches = JobCVMatch.objects.filter(job_id=job_id).select_related(
                "job", "application__applicant__user"
            )

            # Sắp xếp theo điểm từ cao đến thấp
            matches = matches.order_by("-match_score")

            # Thêm thông tin về số lượng applications đã được đánh giá
            from application.models import JobApplication

            total_applications = JobApplication.objects.filter(job_id=job_id).count()
            processed_applications = matches.count()

            serializer = JobCVMatchSerializer(matches, many=True)
            return Response(
                {
                    "total_applications": total_applications,
                    "processed_applications": processed_applications,
                    "results": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Error getting match results: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TaskStatusView(APIView):
    """
    API view để kiểm tra trạng thái của task
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, task_id, format=None):
        """
        Kiểm tra trạng thái của task
        """
        task_result = AsyncResult(task_id)
        return Response(
            {
                "task_id": task_id,
                "status": task_result.status,
                "result": task_result.result if task_result.ready() else None,
            }
        )
