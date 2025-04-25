from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404

from jobs.models import Job, JobApplication
from jobs.serializers import JobSerializer, JobApplicationSerializer
from jobs.permissions import (
    IsApplicationOwnerOrJobRecruiter,
    IsApplicant,
    IsRecruiter,
)
from users.choices import JobStatus, ApplicationStatus, Role
from users.utils import CustomPagination


class JobApplyView(APIView):
    """API to apply for a job"""

    permission_classes = [IsAuthenticated, IsApplicant]

    def post(self, request, pk):
        job = get_object_or_404(Job, id=pk)
        user = request.user

        # Check if job is open
        if job.status != JobStatus.PUBLISHED:
            return Response(
                {
                    "detail": "Cannot apply for this job as it is closed or not published yet"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user already applied
        if JobApplication.objects.filter(applicant=user, job=job).exists():
            return Response(
                {"detail": "You have already applied for this job"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create application
        note = request.data.get("note", "")
        application = JobApplication.objects.create(
            applicant=user, job=job, status=ApplicationStatus.PENDING, note=note
        )

        # Return application info
        serializer = JobApplicationSerializer(application)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# --- Application Views ---
class ApplicationListView(APIView):
    """API to get list of job applications"""

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request):
        user = request.user
        queryset = JobApplication.objects.select_related(
            "job", "job__company", "applicant"
        )

        # If applicant, only see their own applications
        if user.role == Role.APPLICANT:
            queryset = queryset.filter(applicant=user)

        # If recruiter, only see applications for their company's jobs
        elif user.role == Role.RECRUITER:
            company = user.recruiter_profile.company
            if company:
                queryset = queryset.filter(job__company=company)
            else:
                # If recruiter has no company, return empty list
                queryset = JobApplication.objects.none()

        # Apply filters
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        job_filter = request.query_params.get("job")
        if job_filter:
            queryset = queryset.filter(job_id=job_filter)

        # Apply order
        ordering = request.query_params.get("ordering", "-created_at")
        if ordering:
            queryset = queryset.order_by(ordering)

        # Paginate
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize and return
        serializer = JobApplicationSerializer(
            paginated_queryset, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)


class ApplicationDetailView(APIView):
    """API to view application details"""

    permission_classes = [IsAuthenticated, IsApplicationOwnerOrJobRecruiter]

    def get(self, request, pk):
        application = get_object_or_404(
            JobApplication.objects.select_related("job", "job__company", "applicant"),
            id=pk,
        )

        # Check permissions
        self.check_object_permissions(request, application)

        # Return application details
        serializer = JobApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)


class ApplicationUpdateView(APIView):
    """API to update application status"""

    permission_classes = [IsAuthenticated, IsApplicationOwnerOrJobRecruiter]

    def patch(self, request, pk):
        application = get_object_or_404(
            JobApplication.objects.select_related("job", "job__company", "applicant"),
            id=pk,
        )

        # Check permissions
        self.check_object_permissions(request, application)

        # Only recruiters can update application status
        if request.user.role != Role.RECRUITER:
            return Response(
                {"detail": "Only recruiters can change the application status"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if job is closed
        if application.job.status == JobStatus.CLOSED and "status" in request.data:
            new_status = request.data.get("status")
            if new_status != ApplicationStatus.REJECTED:
                return Response(
                    {"detail": "Cannot update application for a closed job"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Update application
        serializer = JobApplicationSerializer(
            application, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()

            # Send notification email (implement later)
            # from .services import JobApplicationService
            # JobApplicationService.notify_applicant_status_change(application)

            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
