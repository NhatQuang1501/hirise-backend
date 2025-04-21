import django_filters
from .models import Job, JobApplication
from users.choices import JobStatus, ApplicationStatus
from django.db.models import Q


class JobFilter(django_filters.FilterSet):
    """Filter tùy chỉnh cho model Job"""

    min_salary_range = django_filters.NumberFilter(
        field_name="min_salary", lookup_expr="gte"
    )
    max_salary_range = django_filters.NumberFilter(
        field_name="max_salary", lookup_expr="lte"
    )

    keywords = django_filters.CharFilter(method="filter_keywords")
    location = django_filters.CharFilter(
        field_name="company__locations__city", lookup_expr="icontains"
    )
    industry = django_filters.CharFilter(
        field_name="company__industries__name", lookup_expr="icontains"
    )
    skills = django_filters.CharFilter(
        field_name="company__skills__name", lookup_expr="icontains"
    )

    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Job
        fields = {
            "status": ["exact"],
            "job_type": ["exact"],
            "experience_level": ["exact"],
            "currency": ["exact"],
            "company": ["exact"],
        }

    def filter_keywords(self, queryset, name, value):
        """Tìm kiếm theo từ khóa trong nhiều trường"""
        if value:
            # Tách từ khóa bằng dấu cách và tìm kiếm
            keywords = value.split()
            query = Q()
            for keyword in keywords:
                query |= (
                    Q(title__icontains=keyword)
                    | Q(description__icontains=keyword)
                    | Q(requirements__icontains=keyword)
                    | Q(responsibilities__icontains=keyword)
                    | Q(company__name__icontains=keyword)
                )
            return queryset.filter(query).distinct()
        return queryset


class JobApplicationFilter(django_filters.FilterSet):
    """Filter tùy chỉnh cho model JobApplication"""

    job_title = django_filters.CharFilter(
        field_name="job__title", lookup_expr="icontains"
    )
    company_name = django_filters.CharFilter(
        field_name="job__company__name", lookup_expr="icontains"
    )
    applicant_name = django_filters.CharFilter(method="filter_applicant_name")
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = JobApplication
        fields = {
            "status": ["exact"],
            "job": ["exact"],
            "applicant": ["exact"],
        }

    def filter_applicant_name(self, queryset, name, value):
        """Tìm kiếm theo tên ứng viên"""
        if value:
            return queryset.filter(
                Q(applicant__username__icontains=value)
                | Q(applicant__applicant_profile__full_name__icontains=value)
            )
        return queryset
