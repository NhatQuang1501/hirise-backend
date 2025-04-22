from django.urls import path
from . import views

app_name = "jobs"

urlpatterns = [
    # Job endpoints
    path("jobs/", views.JobListView.as_view(), name="job-list"),
    path("jobs/create/", views.JobCreateView.as_view(), name="job-create"),
    path("jobs/<uuid:id>/", views.JobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:id>/update/", views.JobUpdateView.as_view(), name="job-update"),
    path(
        "jobs/<uuid:id>/status/",
        views.JobStatusUpdateView.as_view(),
        name="job-status-update",
    ),
    path("jobs/<uuid:id>/apply/", views.JobApplyView.as_view(), name="job-apply"),
    path("jobs/<uuid:id>/save/", views.JobSaveView.as_view(), name="job-save"),
    path(
        "jobs/<uuid:id>/stats/",
        views.JobStatisticsView.as_view(),
        name="job-statistics",
    ),
    # Application endpoints
    path("applications/", views.ApplicationListView.as_view(), name="application-list"),
    path(
        "applications/<uuid:id>/",
        views.ApplicationDetailView.as_view(),
        name="application-detail",
    ),
    path(
        "applications/<uuid:id>/update/",
        views.ApplicationUpdateView.as_view(),
        name="application-update",
    ),
    # SavedJob endpoints
    path("saved-jobs/", views.SavedJobListView.as_view(), name="saved-job-list"),
]
