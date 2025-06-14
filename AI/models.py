from django.db import models
import uuid
import os
from django.conf import settings

# Đường dẫn lưu trữ dữ liệu đã xử lý
JOB_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "job_processed_data")
os.makedirs(JOB_DATA_DIR, exist_ok=True)


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
    Mô hình lưu trữ kết quả đánh giá sự phù hợp giữa job và CV
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.CASCADE, related_name="cv_matches"
    )
    application = models.ForeignKey(
        "application.JobApplication", on_delete=models.CASCADE, related_name="job_match"
    )

    # Điểm phù hợp tổng thể (0-100)
    match_score = models.FloatField(default=0.0)

    # Điểm chi tiết cho từng phần
    detailed_scores = models.JSONField(blank=True, null=True)

    # Thời gian đánh giá
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Đảm bảo mỗi cặp job-application chỉ có một bản ghi đánh giá
        unique_together = ("job", "application")
        # Sắp xếp mặc định theo điểm giảm dần
        ordering = ["-match_score"]

    def __str__(self):
        return f"Match score {self.match_score:.2f}% for {self.application} with {self.job.title}"
