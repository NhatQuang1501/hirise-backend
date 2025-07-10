import django_filters
from .models import JobApplication
from users.choices import ApplicationStatus


class JobApplicationFilter(django_filters.FilterSet):
    """
    Filter cho JobApplication
    """

    status = django_filters.ChoiceFilter(choices=ApplicationStatus.choices)
    created_at_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_at_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
    job = django_filters.UUIDFilter(field_name="job__id")
    match_score_min = django_filters.NumberFilter(
        field_name="cv_analysis__match_score", lookup_expr="gte"
    )
    match_score_max = django_filters.NumberFilter(
        field_name="cv_analysis__match_score", lookup_expr="lte"
    )

    class Meta:
        model = JobApplication
        fields = [
            "status",
            "job",
            "created_at_after",
            "created_at_before",
            "match_score_min",
            "match_score_max",
        ]
