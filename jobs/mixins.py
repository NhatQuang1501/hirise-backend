from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from jobs.models import JobApplication, JobView, SavedJob
from jobs.serializers import JobApplicationCreateSerializer
from users.choices import JobStatus, ApplicationStatus


class JobViewMixin:
    """
    Mixin cung cấp các phương thức chung cho JobViewSet
    """

    @action(detail=True, methods=["post"], url_path="track-view")
    def track_view(self, request, pk=None):
        """Theo dõi lượt xem job"""
        job = self.get_object()

        # Lưu lượt xem
        JobView.objects.create(
            job=job, user=request.user if request.user.is_authenticated else None
        )

        return Response({"message": "Đã ghi nhận lượt xem"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="save")
    def save_job(self, request, pk=None):
        """Lưu job vào danh sách yêu thích"""
        job = self.get_object()

        # Kiểm tra user đã đăng nhập
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Bạn cần đăng nhập để lưu job"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Kiểm tra xem đã lưu chưa
        if SavedJob.objects.filter(user=request.user, job=job).exists():
            return Response(
                {"detail": "Bạn đã lưu job này rồi"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Lưu job
        SavedJob.objects.create(user=request.user, job=job)

        return Response(
            {"message": "Saved job successfully"}, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="unsave")
    def unsave_job(self, request, pk=None):
        """Bỏ lưu job khỏi danh sách yêu thích"""
        job = self.get_object()

        # Kiểm tra user đã đăng nhập
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Bạn cần đăng nhập để thực hiện hành động này"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Tìm và xóa saved job
        saved_job = SavedJob.objects.filter(user=request.user, job=job).first()
        if not saved_job:
            return Response(
                {"detail": "You have not saved this job"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        saved_job.delete()

        return Response(
            {"message": "Unsaved job successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="apply")
    def apply_job(self, request, pk=None):
        """Ứng tuyển vào job"""
        job = self.get_object()

        # Kiểm tra user đã đăng nhập
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Bạn cần đăng nhập để ứng tuyển"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Kiểm tra role của user
        if request.user.role != "applicant":
            return Response(
                {"detail": "Chỉ ứng viên mới có thể ứng tuyển"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Kiểm tra job có đang mở không
        if job.status != JobStatus.PUBLISHED:
            return Response(
                {
                    "detail": "Không thể ứng tuyển vào job này do đã đóng hoặc chưa đăng tải"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra đã ứng tuyển chưa
        if JobApplication.objects.filter(applicant=request.user, job=job).exists():
            return Response(
                {"detail": "Bạn đã ứng tuyển vào job này rồi"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Lấy note từ request
        note = request.data.get("note", "")

        # Tạo đơn ứng tuyển
        serializer = JobApplicationCreateSerializer(
            data={"job": job.id, "note": note}, context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Ứng tuyển thành công",
                "application_id": serializer.instance.id,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="statistics")
    def statistics(self, request, pk=None):
        """Lấy thống kê về job"""
        job = self.get_object()

        # Kiểm tra quyền - chỉ nhà tuyển dụng sở hữu job được xem thống kê
        if not request.user.is_authenticated or request.user.role != "recruiter":
            return Response(
                {"detail": "Bạn không có quyền xem thống kê của job này"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Kiểm tra xem nhà tuyển dụng có thuộc công ty sở hữu job không
        if job.company != request.user.recruiter_profile.company:
            return Response(
                {
                    "detail": "Bạn không phải là nhà tuyển dụng của công ty sở hữu job này"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Lấy thống kê
        from .services import JobService

        stats = JobService.get_job_statistics(job)

        return Response(stats, status=status.HTTP_200_OK)
