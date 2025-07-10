from django.urls import path
from .views import (
    JobApplicationListCreateView,
    JobApplicationDetailView,
    JobApplicationAnalyzeView,
    JobApplicationStatusView,
    CVAnalysisListView,
    CVAnalysisDetailView,
    TestFileUploadView,
    TestFileUploadDetailView,
)

urlpatterns = [
    path(
        "applications/",
        JobApplicationListCreateView.as_view(),
        name="application-list-create",
    ),
    path(
        "applications/<uuid:pk>/",
        JobApplicationDetailView.as_view(),
        name="application-detail",
    ),
    path(
        "applications/<uuid:pk>/analyze/",
        JobApplicationAnalyzeView.as_view(),
        name="application-analyze",
    ),
    path(
        "applications/<uuid:pk>/<str:action>/",
        JobApplicationStatusView.as_view(),
        name="application-status",
    ),
    path("cv-analyses/", CVAnalysisListView.as_view(), name="cv-analysis-list"),
    path(
        "cv-analyses/<uuid:pk>/",
        CVAnalysisDetailView.as_view(),
        name="cv-analysis-detail",
    ),
    # Test file upload endpoints
    path("test-uploads/", TestFileUploadView.as_view(), name="test-file-upload"),
    path(
        "test-uploads/<uuid:pk>/",
        TestFileUploadDetailView.as_view(),
        name="test-file-upload-detail",
    ),
]
