from . import models
from django.db import models
import unicodedata


class Enum(models.TextChoices):
    @classmethod
    def get_choices_display(cls):
        return [choice[1] for choice in cls.choices]

    @classmethod
    def map_display_to_value(cls, display):
        display_normalized = unicodedata.normalize("NFC", str(display).strip().lower())

        for choice in cls.choices:
            label = choice[1]
            label_normalized = unicodedata.normalize("NFC", str(label).strip().lower())
            if label_normalized == display_normalized:
                return choice[0]
        return None

    @classmethod
    def map_value_to_display(cls, value):
        for choice in cls.choices:
            if choice[0] == value:
                return choice[1]
        return None


class Role(Enum):
    APPLICANT = "applicant"
    ADMIN = "admin"
    RECRUITER = "recruiter"


class Gender(Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Currency(Enum):
    VND = "VND"
    USD = "USD"
    EUR = "EUR"
    JPY = "JPY"


class JobStatus(Enum):
    PUBLISHED = "published"
    DRAFT = "draft"
    CLOSED = "closed"


class ReportType(Enum):
    JOB = "job"
    COMMENT = "comment"
    USER = "user"


class NotificationType:
    POST = "post"
    REPORT = "report"
