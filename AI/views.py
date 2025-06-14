from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.http import Http404
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

            try:
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

            matching_service = MatchingService()
            result = matching_service.match_job_cv(
                job_id, application_id=application_id
            )

            if result:
                serializer = JobCVMatchSerializer(result)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Cannot evaluate match"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return Response(
                {"error": f"Error evaluating match: {str(e)}"},
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
            # Cập nhật trạng thái của tất cả application đang ở trạng thái pending
            from application.models import JobApplication
            from users.choices import ApplicationStatus

            pending_applications = JobApplication.objects.filter(
                job_id=job_id, status=ApplicationStatus.PENDING
            )

            # Cập nhật trạng thái thành reviewing
            if pending_applications.exists():
                pending_applications.update(status=ApplicationStatus.REVIEWING)

            matching_service = MatchingService()
            results = matching_service.match_job_with_all_applications(job_id)

            serializer = JobCVMatchSerializer(results, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
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
            matches = JobCVMatch.objects.filter(job_id=job_id).select_related(
                "job", "application__applicant__user"
            )

            # Sắp xếp theo điểm từ cao đến thấp
            matches = matches.order_by("-match_score")

            serializer = JobCVMatchSerializer(matches, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Error getting match results: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
