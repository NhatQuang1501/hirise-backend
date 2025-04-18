from django.db import models


class BaseChoices(models.TextChoices):
    @classmethod
    def get_values(cls):
        """Return list of values only"""
        return [choice[0] for choice in cls.choices]

    @classmethod
    def get_labels(cls):
        """Return list of labels only"""
        return [choice[1] for choice in cls.choices]


class Role(BaseChoices):
    APPLICANT = "applicant", "Applicant"
    ADMIN = "admin", "Admin"
    RECRUITER = "recruiter", "Recruiter"


class Gender(BaseChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


class Currency(BaseChoices):
    VND = "VND", "VND"
    USD = "USD", "USD"
    EUR = "EUR", "EUR"
    JPY = "JPY", "JPY"


class JobStatus(BaseChoices):
    PUBLISHED = "published", "Published"
    DRAFT = "draft", "Draft"
    CLOSED = "closed", "Closed"


class PlatformChoices(BaseChoices):
    FACEBOOK = "facebook", "Facebook"
    LINKEDIN = "linkedin", "LinkedIn"
    GITHUB = "github", "GitHub"
    PORTFOLIO = "portfolio", "Portfolio"
    OTHERS = "others", "Others"


class UserStatusChoices(BaseChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    PENDING = "pending", "Pending"
    SUSPENDED = "suspended", "Suspended"


class ApplicationStatusChoices(BaseChoices):
    PENDING = "pending", "Pending Review"
    REVIEWING = "reviewing", "Under Review"
    SHORTLISTED = "shortlisted", "Shortlisted"
    INTERVIEWED = "interviewed", "Interviewed"
    OFFERED = "offered", "Job Offered"
    ACCEPTED = "accepted", "Offer Accepted"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"


class JobTypeChoices(BaseChoices):
    FULL_TIME = "full_time", "Full Time"
    PART_TIME = "part_time", "Part Time"
    CONTRACT = "contract", "Contract"
    INTERNSHIP = "internship", "Internship"
    FREELANCE = "freelance", "Freelance"


class ExperienceLevelChoices(BaseChoices):
    INTERN = "intern", "Intern"
    FRESHER = "fresher", "Fresher"
    JUNIOR = "junior", "Junior (1-3 years)"
    MIDDLE = "middle", "Middle (3-5 years)"
    SENIOR = "senior", "Senior (5+ years)"
    LEAD = "lead", "Team Lead/Manager"
    EXPERT = "expert", "Expert/Director"
