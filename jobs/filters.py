import django_filters
from jobs.models import Job
from users.choices import JobStatus, JobType, ExperienceLevel


class JobFilter(django_filters.FilterSet):
    """Filter cho Job model"""

    # Filter các trường cơ bản
    title = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=JobStatus.choices)
    job_type = django_filters.ChoiceFilter(choices=JobType.choices)
    experience_level = django_filters.ChoiceFilter(choices=ExperienceLevel.choices)

    # Filter cho mức lương
    min_salary_gte = django_filters.NumberFilter(
        field_name="min_salary", lookup_expr="gte"
    )
    max_salary_lte = django_filters.NumberFilter(
        field_name="max_salary", lookup_expr="lte"
    )

    # Filter cho ngày tạo/cập nhật
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

    # Filter cho công ty
    company = django_filters.CharFilter(
        field_name="company__name", lookup_expr="icontains"
    )
    company_id = django_filters.UUIDFilter(field_name="company__id")

    # Filter cho địa điểm
    location = django_filters.CharFilter(
        field_name="company__locations__city", lookup_expr="icontains"
    )
    country = django_filters.CharFilter(
        field_name="company__locations__country", lookup_expr="icontains"
    )

    # Filter cho kỹ năng
    skills = django_filters.CharFilter(
        field_name="company__skills__name", lookup_expr="icontains"
    )

    # Filter cho ngành nghề
    industry = django_filters.CharFilter(
        field_name="company__industries__name", lookup_expr="icontains"
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "status",
            "job_type",
            "experience_level",
            "min_salary_gte",
            "max_salary_lte",
            "created_after",
            "created_before",
            "updated_after",
            "updated_before",
            "company",
            "company_id",
            "location",
            "country",
            "skills",
            "industry",
        ]
