from django.db import models
from django.contrib.auth.models import Group, Permission
import uuid
from users.choices import *
from users.models import User


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True, default="Vietnam")
    address = models.TextField(blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

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


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=100, unique=True)
    name = models.CharField(max_length=50)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="company_logos/", blank=True)
    description = models.TextField(blank=True)
    benefits = models.TextField(blank=True)
    founded_year = models.IntegerField(blank=True, null=True)

    locations = models.ManyToManyField(
        Location,
        related_name="companies",
        blank=True,
    )

    industries = models.ManyToManyField(
        Industry,
        related_name="companies",
        blank=True,
    )
    # Tag kỹ năng liên quan đến công ty
    skills = models.ManyToManyField(
        SkillTag,
        related_name="companies",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def company_id(self):
        return self.id


class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="jobs",
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

    min_salary = models.IntegerField(blank=True, null=True)
    max_salary = models.IntegerField(blank=True, null=True)
    currency = models.CharField(
        max_length=5,
        choices=Currency.choices,
        default=Currency.VND,
    )
    is_salary_negotiable = models.BooleanField(default=True)
    closed_date = models.DateField(blank=True, null=True)

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
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="saved_job")
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_job_user"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "job")

    def __str__(self):
        return f"{self.user.username} saved {self.job.title}"

    @property
    def savedJob_id(self):
        return self.id


class JobApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        User,  # Hoặc ApplicantProfile nếu muốn rõ hơn
        on_delete=models.CASCADE,
        related_name="applications",
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
    )
    note = models.TextField(blank=True)

    class Meta:
        unique_together = ("applicant", "job")  # Tránh apply nhiều lần

    def __str__(self):
        return f"{self.applicant.username} - {self.job.title}"

    @property
    def jobApplication_id(self):
        return self.id


class InterviewSchedule(models.Model):
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


class CVReview(models.Model):
    application = models.OneToOneField(
        JobApplication,
        on_delete=models.CASCADE,
        related_name="cv_review",
    )
    match_score = models.FloatField()  # 0-100%
    summary = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.application}"


class JobView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="views",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Viewed {self.job.title} at {self.viewed_at}"

    @property
    def jobView_id(self):
        return self.id
