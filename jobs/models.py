from django.db import models
from django.contrib.auth.models import Group, Permission
import uuid
from users.choices import *
from django.core.exceptions import ValidationError


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    address = models.TextField()  # Trường chính để lưu địa chỉ đầy đủ
    country = models.CharField(max_length=100, blank=True, default="Vietnam")
    description = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.address

    @property
    def location_id(self):
        return self.id


class Industry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    @property
    def industry_id(self):
        return self.id


class SkillTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    @property
    def skillTag_id(self):
        return self.id


class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "users.CompanyProfile",
        on_delete=models.CASCADE,
        related_name="company_jobs",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    responsibilities = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    benefits = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.DRAFT,
    )
    job_type = models.CharField(
        max_length=20,
        choices=JobType.choices,
        blank=True,
    )
    experience_level = models.CharField(
        max_length=20,
        choices=ExperienceLevel.choices,
        blank=True,
    )
    city = models.CharField(
        max_length=20,
        choices=City.choices,
        blank=True,
    )

    min_salary = models.IntegerField(blank=True, null=True)
    max_salary = models.IntegerField(blank=True, null=True)
    currency = models.CharField(
        max_length=5,
        choices=Currency.choices,
        default=Currency.VND,
    )
    is_salary_negotiable = models.BooleanField(default=True)
    closed_date = models.DateField(blank=True, null=True)

    # Thêm các liên kết
    locations = models.ManyToManyField(
        Location,
        related_name="jobs",
        blank=True,
    )
    industries = models.ManyToManyField(
        Industry,
        related_name="jobs",
        blank=True,
    )
    skills = models.ManyToManyField(
        SkillTag,
        related_name="jobs",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def job_id(self):
        return self.id

    @property
    def salary_display(self):
        if self.is_salary_negotiable:
            return "Negotiable"
        if self.min_salary and self.max_salary:
            return f"{self.min_salary:,} - {self.max_salary:,} {self.currency}"
        elif self.min_salary:
            return f"From {self.min_salary:,} {self.currency}"
        elif self.max_salary:
            return f"Up to {self.max_salary:,} {self.currency}"
        return "Not specified"


class SavedJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="saved_by")
    # Sử dụng string để tránh circular import
    applicant = models.ForeignKey(
        "users.ApplicantProfile", on_delete=models.CASCADE, related_name="saved_jobs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("applicant", "job")

    def __str__(self):
        return f"{self.applicant.user.username if hasattr(self.applicant, 'user') else 'Unknown'} saved {self.job.title}"

    @property
    def savedJob_id(self):
        return self.id


class JobStatistics(models.Model):
    job = models.OneToOneField(
        Job,
        on_delete=models.CASCADE,
        related_name="statistics",
    )
    view_count = models.IntegerField(default=0)
    application_count = models.IntegerField(default=0)
    accepted_count = models.IntegerField(default=0)
    rejected_count = models.IntegerField(default=0)
    average_processing_time = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"Statistics for {self.job.title}"


class CompanyStatistics(models.Model):
    company = models.OneToOneField(
        "users.CompanyProfile",
        on_delete=models.CASCADE,
        related_name="statistics",
    )
    total_jobs = models.IntegerField(default=0)
    active_jobs = models.IntegerField(default=0)
    total_applications = models.IntegerField(default=0)
    hired_applicants = models.IntegerField(default=0)
    average_hire_rate = models.FloatField(default=0)

    def __str__(self):
        return f"Statistics for {self.company.name}"
