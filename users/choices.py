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
    COMPANY = "company", "Company"


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


class Platform(BaseChoices):
    FACEBOOK = "facebook", "Facebook"
    LINKEDIN = "linkedin", "LinkedIn"
    GITHUB = "github", "GitHub"
    PORTFOLIO = "portfolio", "Portfolio"
    OTHERS = "others", "Others"


class UserStatus(BaseChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    PENDING = "pending", "Pending"
    SUSPENDED = "suspended", "Suspended"


class ApplicationStatus(BaseChoices):
    PENDING = "pending", "Pending Review"
    REVIEWING = "reviewing", "Reviewing"
    PROCESSING = "processing", "Processing"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"


class JobType(BaseChoices):
    FULL_TIME = "full time", "Full Time"
    PART_TIME = "part time", "Part Time"
    CONTRACT = "contract", "Contract"
    FREELANCE = "freelance", "Freelance"


class ExperienceLevel(BaseChoices):
    INTERN = "intern", "Intern"
    FRESHER = "fresher", "Fresher"
    JUNIOR = "junior", "Junior (1-3 years)"
    MIDDLE = "middle", "Middle (3-5 years)"
    SENIOR = "senior", "Senior (5+ years)"
    LEAD = "lead", "Lead"
    MANAGER = "manager", "Manager"


class City(BaseChoices):
    HANOI = "hanoi", "Ha Noi"
    HOCHIMINH = "hochiminh", "Ho Chi Minh"
    DANANG = "danang", "Da Nang"
    HUE = "hue", "Hue"
    CANTHO = "cantho", "Can Tho"
    OTHERS = "others", "Others"
