from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from users.choices import *
import uuid


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(max_length=100, unique=True)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=100)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.APPLICANT,
    )

    is_verified = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    locked_reason = models.TextField(blank=True)
    locked_date = models.DateTimeField(blank=True, null=True)
    unlocked_date = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
    )
    phone_number = models.CharField(max_length=20, blank=True)

    cv = models.FileField(upload_to="cv/", blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.full_name}"

    @property
    def applicant_id(self):
        return self.user.id

    @property
    def social_links_data(self):
        return [
            {
                "platform": link.platform,
                "url": link.url,
                "custom_label": link.custom_label,
            }
            for link in self.user.social_links.all()
        ]


class CompanyProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="company_profile",
    )
    name = models.CharField(max_length=50)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="company_logos/", blank=True)
    description = models.TextField(blank=True)
    benefits = models.TextField(blank=True)
    founded_year = models.IntegerField(blank=True, null=True)
    follower_count = models.IntegerField(default=0)

    locations = models.ManyToManyField(
        "jobs.Location",
        related_name="company_profiles",
        blank=True,
    )
    industries = models.ManyToManyField(
        "jobs.Industry",
        related_name="company_profiles",
        blank=True,
    )
    skills = models.ManyToManyField(
        "jobs.SkillTag",
        related_name="company_profiles",
        blank=True,
    )

    def __str__(self):
        return f"{self.user.username} - {self.name}"

    @property
    def company_id(self):
        return self.user.id

    @property
    def social_links_dict(self):
        return {link.platform: link.url for link in self.user.social_links.all()}


class SocialLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_links",
    )
    platform = models.CharField(
        max_length=50,
        choices=Platform.choices,
    )
    url = models.URLField(blank=True, null=True)
    custom_label = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ("user", "platform")

    def __str__(self):
        return f"{self.user.username} - {self.platform} - {self.url}"

    @property
    def socialLink_id(self):
        return self.id


class CompanyFollower(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        ApplicantProfile,
        on_delete=models.CASCADE,
        related_name="following_companies",
    )
    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("applicant", "company")
        verbose_name = "Company Follower"
        verbose_name_plural = "Company Followers"

    def __str__(self):
        return f"{self.applicant.full_name} follows {self.company.name}"

    @property
    def follower_id(self):
        return self.id
