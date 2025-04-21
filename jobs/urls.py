from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import JobViewSet, JobApplicationViewSet

router = DefaultRouter()
router.register(r"jobs", JobViewSet)
router.register(r"applications", JobApplicationViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
