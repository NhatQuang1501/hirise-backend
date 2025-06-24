from django.db import models
import uuid
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Đường dẫn lưu trữ dữ liệu đã xử lý
JOB_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "job_processed_data")
CV_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "cv_processed_data")

# Đảm bảo thư mục tồn tại
try:
    os.makedirs(JOB_DATA_DIR, exist_ok=True)
    os.makedirs(CV_DATA_DIR, exist_ok=True)
    logger.info(f"Created directories: {JOB_DATA_DIR} and {CV_DATA_DIR}")
except Exception as e:
    logger.error(f"Error creating directories: {e}")


class JobProcessedData(models.Model):
    """
    Mô hình lưu trữ dữ liệu job đã được xử lý cho SBERT
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="processed_data",
    )

    # Dữ liệu đã được phân tách
    title = models.TextField(blank=True)
    description = models.TextField(blank=True)
    skills = models.JSONField(blank=True, null=True)
    industry = models.TextField(blank=True)
    experience_level = models.CharField(max_length=50, blank=True)

    # Phân tách requirements
    basic_requirements = models.TextField(blank=True)
    preferred_skills = models.TextField(blank=True)

    responsibilities = models.TextField(blank=True)

    # Dữ liệu đã được kết hợp cho SBERT
    combined_text = models.TextField(blank=True)

    # Thông tin yêu cầu kinh nghiệm
    experience_requirements = models.JSONField(blank=True, null=True, default=dict)

    # Đường dẫn đến file lưu vector embedding
    embedding_file = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Processed data for {self.job.title}"


class CVProcessedData(models.Model):
    """
    Mô hình lưu trữ dữ liệu CV đã được xử lý cho SBERT
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        "application.JobApplication",
        on_delete=models.CASCADE,
        related_name="processed_cv",
    )

    # Dữ liệu đã được phân tách
    summary = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    education = models.TextField(blank=True)
    skills = models.TextField(blank=True)
    projects = models.TextField(blank=True)
    certifications = models.TextField(blank=True)
    languages = models.TextField(blank=True)
    achievements = models.TextField(blank=True)

    # Danh sách kỹ năng đã trích xuất
    extracted_skills = models.JSONField(blank=True, null=True)

    # Chi tiết kinh nghiệm (số năm kinh nghiệm với từng công nghệ)
    experience_details = models.JSONField(blank=True, null=True, default=dict)

    # Nội dung đầy đủ
    full_text = models.TextField(blank=True)

    # Dữ liệu đã được kết hợp cho SBERT
    combined_text = models.TextField(blank=True)

    # Đường dẫn đến file lưu vector embedding
    embedding_file = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Processed CV for {self.application}"


class JobCVMatch(models.Model):
    """
    Mô hình lưu trữ kết quả đánh giá độ phù hợp giữa job và CV
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="cv_matches",
    )
    application = models.ForeignKey(
        "application.JobApplication",
        on_delete=models.CASCADE,
        related_name="job_matches",
        null=True,
        blank=True,
    )
    cv_processed_data = models.ForeignKey(
        CVProcessedData,
        on_delete=models.CASCADE,
        related_name="job_matches",
        null=True,
        blank=True,
    )

    # Điểm số tổng hợp
    match_score = models.FloatField(default=0)

    # Điểm số chi tiết cho từng phần
    detail_scores = models.JSONField(blank=True, null=True)

    # Thêm trường match_details
    match_details = models.JSONField(default=dict)

    # Phân tích chi tiết về điểm mạnh/yếu
    strengths = models.JSONField(blank=True, null=True)
    weaknesses = models.JSONField(blank=True, null=True)

    # Giải thích về kết quả đánh giá
    explanation = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("job", "application")

    def __str__(self):
        return f"Match between {self.job.title} and Application {self.application_id}"
