from django.urls import path
from jobs.views.job_views import *
from jobs.views.job_application_views import *

app_name = "jobs"

urlpatterns = [
    # Job endpoints
    path("", JobListView.as_view(), name="job-list"),
    path("create/", JobCreateView.as_view(), name="job-create"),
    path("<uuid:pk>/", JobDetailView.as_view(), name="job-detail"),
    path("<uuid:pk>/update/", JobUpdateView.as_view(), name="job-update"),
    path("<uuid:pk>/delete/", JobDeleteView.as_view(), name="job-delete"),
    path(
        "<uuid:pk>/status/",
        JobStatusUpdateView.as_view(),
        name="job-status-update",
    ),
    path("<uuid:pk>/apply/", JobApplyView.as_view(), name="job-apply"),
    path("<uuid:pk>/save/", JobSaveView.as_view(), name="job-save"),
    path("<uuid:pk>/stats/", JobStatisticsView.as_view(), name="job-statistics"),
    path("auto-close/", AutoCloseJobsView.as_view(), name="job-auto-close"),
    # Application endpoints
    path("applications/", ApplicationListView.as_view(), name="application-list"),
    path(
        "applications/<uuid:pk>/",
        ApplicationDetailView.as_view(),
        name="application-detail",
    ),
    path(
        "applications/<uuid:pk>/update/",
        ApplicationUpdateView.as_view(),
        name="application-update",
    ),
    # SavedJob endpoints
    path("saved/", SavedJobListView.as_view(), name="saved-job-list"),
]
