from django.urls import path
from jobs.views.job_views import (
    JobListView,
    JobDetailView,
    JobCreateView,
    JobUpdateView,
    JobDeleteView,
    JobStatusUpdateView,
    AutoCloseJobsView,
    JobSaveView,
    JobStatisticsView,
    SavedJobListView,
    ApplicantSavedJobsView,
    CompanyJobsView,
    CompanyStatisticsView,
)
from jobs.views.job_application_views import (
    JobApplicationListView,
    JobApplicationDetailView,
    JobApplicationCreateView,
    JobApplicationUpdateStatusView,
    JobApplicationsForJobView,
    ApplicantApplicationsView,
    InterviewScheduleView,
    CVReviewView,
)

app_name = "jobs"

urlpatterns = [
    # Job endpoints
    path("jobs/", JobListView.as_view(), name="job-list"),
    path("jobs/<uuid:pk>/", JobDetailView.as_view(), name="job-detail"),
    path("jobs/create/", JobCreateView.as_view(), name="job-create"),
    path("jobs/<uuid:pk>/update/", JobUpdateView.as_view(), name="job-update"),
    path("jobs/<uuid:pk>/delete/", JobDeleteView.as_view(), name="job-delete"),
    path(
        "jobs/<uuid:pk>/status/",
        JobStatusUpdateView.as_view(),
        name="job-status-update",
    ),
    path("jobs/auto-close/", AutoCloseJobsView.as_view(), name="job-auto-close"),
    path("jobs/<uuid:pk>/save/", JobSaveView.as_view(), name="job-save"),
    path(
        "jobs/<uuid:pk>/statistics/", JobStatisticsView.as_view(), name="job-statistics"
    ),
    # Company jobs and statistics
    path(
        "companies/<uuid:company_id>/jobs/",
        CompanyJobsView.as_view(),
        name="company-jobs",
    ),
    path(
        "companies/<uuid:company_id>/statistics/",
        CompanyStatisticsView.as_view(),
        name="company-statistics",
    ),
    # Saved job endpoints
    path("saved-jobs/", SavedJobListView.as_view(), name="saved-job-list"),
    path(
        "applicants/<uuid:applicant_id>/saved-jobs/",
        ApplicantSavedJobsView.as_view(),
        name="applicant-saved-jobs",
    ),
    # Job application endpoints
    path("applications/", JobApplicationListView.as_view(), name="application-list"),
    path(
        "applications/<uuid:pk>/",
        JobApplicationDetailView.as_view(),
        name="application-detail",
    ),
    path(
        "jobs/<uuid:job_id>/apply/",
        JobApplicationCreateView.as_view(),
        name="application-create",
    ),
    path(
        "applications/<uuid:pk>/status/",
        JobApplicationUpdateStatusView.as_view(),
        name="application-status-update",
    ),
    path(
        "jobs/<uuid:job_id>/applications/",
        JobApplicationsForJobView.as_view(),
        name="job-applications",
    ),
    path(
        "applicants/<uuid:applicant_id>/applications/",
        ApplicantApplicationsView.as_view(),
        name="applicant-applications",
    ),
    # Interview schedule endpoints
    path(
        "applications/<uuid:application_id>/interview/",
        InterviewScheduleView.as_view(),
        name="interview-schedule",
    ),
    # CV review endpoints
    path(
        "applications/<uuid:application_id>/cv-review/",
        CVReviewView.as_view(),
        name="cv-review",
    ),
]
