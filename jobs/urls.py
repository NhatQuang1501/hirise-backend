from django.urls import path
from jobs.views.job_views import *
from jobs.views.job_application_views import *

app_name = "jobs"

urlpatterns = [
    # Job endpoints
    path("jobs/", JobListView.as_view(), name="job-list"),
    path("jobs/create/", JobCreateView.as_view(), name="job-create"),
    path("jobs/<uuid:id>/", JobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:id>/update/", JobUpdateView.as_view(), name="job-update"),
    path(
        "jobs/<uuid:id>/status/",
        JobStatusUpdateView.as_view(),
        name="job-status-update",
    ),
    path("jobs/<uuid:id>/apply/", JobApplyView.as_view(), name="job-apply"),
    path("jobs/<uuid:id>/save/", JobSaveView.as_view(), name="job-save"),
    path(
        "jobs/<uuid:id>/stats/",
        JobStatisticsView.as_view(),
        name="job-statistics",
    ),
    path("saved-jobs/", SavedJobListView.as_view(), name="saved-job-list"),
    # Application endpoints
    path("applications/", ApplicationListView.as_view(), name="application-list"),
    path(
        "applications/<uuid:id>/",
        ApplicationDetailView.as_view(),
        name="application-detail",
    ),
    path(
        "applications/<uuid:id>/update/",
        ApplicationUpdateView.as_view(),
        name="application-update",
    ),
]
