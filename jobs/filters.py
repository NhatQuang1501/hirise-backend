import django_filters
from jobs.models import Job
from users.choices import JobStatus, JobType, ExperienceLevel, City


class JobFilter(django_filters.FilterSet):
    """Filter for Job model"""

    # Basic field filters
    title = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=JobStatus.choices)
    job_type = django_filters.ChoiceFilter(choices=JobType.choices)
    experience_level = django_filters.ChoiceFilter(choices=ExperienceLevel.choices)
    city = django_filters.ChoiceFilter(choices=City.choices)

    # Salary filters
    min_salary_gte = django_filters.NumberFilter(
        field_name="min_salary", lookup_expr="gte"
    )
    max_salary_lte = django_filters.NumberFilter(
        field_name="max_salary", lookup_expr="lte"
    )

    # Negotiable salary filter
    is_salary_negotiable = django_filters.BooleanFilter()

    # Date filters
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="lte"
    )
    updated_after = django_filters.DateFilter(
        field_name="updated_at", lookup_expr="gte"
    )
    updated_before = django_filters.DateFilter(
        field_name="updated_at", lookup_expr="lte"
    )

    # Company filters
    company_name = django_filters.CharFilter(
        field_name="company__name", lookup_expr="icontains"
    )
    company_id = django_filters.UUIDFilter(field_name="company__id")

    # Location filters
    location = django_filters.CharFilter(
        field_name="locations__city", lookup_expr="icontains"
    )
    country = django_filters.CharFilter(
        field_name="locations__country", lookup_expr="icontains"
    )

    # Skill filters
    skills = django_filters.CharFilter(
        field_name="skills__name", lookup_expr="icontains"
    )

    # Industry filters
    industry = django_filters.CharFilter(
        field_name="industries__name", lookup_expr="icontains"
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "status",
            "job_type",
            "experience_level",
            "city",
            "min_salary_gte",
            "max_salary_lte",
            "is_salary_negotiable",
            "created_after",
            "created_before",
            "updated_after",
            "updated_before",
            "company_name",
            "company_id",
            "location",
            "country",
            "skills",
            "industry",
        ]


class JobApplicationFilter(django_filters.FilterSet):
    """Filter for JobApplication model"""

    # Status filter
    status = django_filters.ChoiceFilter(choices=JobStatus.choices)

    # Date filters
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="lte"
    )

    # Job filters
    job_title = django_filters.CharFilter(
        field_name="job__title", lookup_expr="icontains"
    )
    job_id = django_filters.UUIDFilter(field_name="job__id")

    # Applicant filters
    applicant_name = django_filters.CharFilter(
        field_name="applicant__full_name", lookup_expr="icontains"
    )
    applicant_id = django_filters.UUIDFilter(field_name="applicant__user__id")
