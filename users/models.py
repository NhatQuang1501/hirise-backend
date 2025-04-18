from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from .enums import *
import uuid
from jobs.models import Company


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(max_length=100, unique=True)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=64)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.APPLICANT,
    )

    is_verified = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    locked_reason = models.TextField(blank=True)
    locked_date = models.DateTimeField(blank=True)
    unlocked_date = models.DateTimeField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    groups = models.ManyToManyField(
        Group,
        related_name="custom_user_set",
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="custom_user_set",
        blank=True,
    )

    def __str__(self):
        return self.username

    @property
    def user_id(self):
        return self.id


class ApplicantProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="applicant_profile",
    )

    full_name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    cv = models.FileField(upload_to="cv/", blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.full_name}"

    @property
    def applicant_id(self):
        return self.user.id

    @property
    def social_links_dict(self):
        return {link.platform: link.url for link in self.social_links.all()}


class RecruiterProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="recruiter_profile",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="recruiters",
        blank=True,
        null=True,
    )

    full_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.full_name}"

    @property
    def recruiter_id(self):
        return self.user.id


class SocialLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    PLATFORM_CHOICES = [
        ("facebook", "Facebook"),
        ("linkedin", "LinkedIn"),
        ("github", "GitHub"),
        ("portfolio", "Portfolio"),
        ("others", "Others"),
    ]

    profile = models.ForeignKey(
        ApplicantProfile,
        on_delete=models.CASCADE,
        related_name="social_links",
    )
    platform = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES,
        on_delete=models.CASCADE,
    )
    url = models.URLField()
    custom_label = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.platform} - {self.url}"

    @property
    def socialLink_id(self):
        return self.id
