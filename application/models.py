from django.db import models
import uuid
from users.choices import ApplicationStatus
from django.contrib.postgres.fields import JSONField
from django.conf import settings
import os


class JobApplication(models.Model):
    """
    Mô hình lưu trữ thông tin ứng tuyển của ứng viên vào công việc
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="job_applications",
    )
    applicant = models.ForeignKey(
        "users.ApplicantProfile",
        on_delete=models.CASCADE,
        related_name="job_applications",
    )
    cv_file = models.FileField(upload_to="cv_applications/", blank=False, null=False)
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("applicant", "job")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.applicant.user.username} - {self.job.title}"

    @property
    def job_application_id(self):
        return self.id

    def get_cv_filename(self):
        return os.path.basename(self.cv_file.name)

    def delete(self, *args, **kwargs):
        # Xóa file CV khi xóa application
        if self.cv_file:
            storage = self.cv_file.storage
            if storage.exists(self.cv_file.name):
                storage.delete(self.cv_file.name)
        super().delete(*args, **kwargs)


class InterviewSchedule(models.Model):
    """
    Mô hình lưu trữ lịch phỏng vấn
    """

    application = models.OneToOneField(
        JobApplication,
        on_delete=models.CASCADE,
        related_name="interview",
    )
    scheduled_time = models.DateTimeField(blank=True, null=True)
    meeting_link = models.URLField(blank=True, null=True)
    note = models.TextField(blank=True)

    def __str__(self):
        return f"Interview for {self.application}"


# Test upload file
class TestFileUpload(models.Model):
    """
    Mô hình test upload file lên storage
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="test_uploads/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def get_file_name(self):
        return os.path.basename(self.file.name)

    def delete(self, *args, **kwargs):
        # Xóa file khi xóa object
        if self.file:
            storage = self.file.storage
            if storage.exists(self.file.name):
                storage.delete(self.file.name)
        super().delete(*args, **kwargs)
