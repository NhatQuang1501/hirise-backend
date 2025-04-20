from django.db import models
from django.contrib.auth.models import Group, Permission
import uuid
from users.enums import Currency


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

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
    description = models.TextField(blank=True, null=True)
    responsibilities = models.TextField(blank=True, null=True)
    requirements = models.TextField(blank=True, null=True)
    benefits = models.TextField(blank=True, null=True)

    min_salary = models.IntegerField(blank=True, null=True)
    max_salary = models.IntegerField(blank=True, null=True)
    currency = models.CharField(
        max_length=5,
        choices=Currency.choices,
        default=Currency.VND,
    )
    is_salary_negotiable = models.BooleanField(default=False)

    expired_date = models.DateField(blank=True)

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
