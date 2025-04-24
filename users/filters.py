from django_filters import rest_framework as filters
from django.db.models import Q
from users.models import User
from users.choices import Role, Gender


class BaseUserFilter(filters.FilterSet):
    search = filters.CharFilter(method="search_fields")
    role = filters.ChoiceFilter(choices=Role.choices)
    created_at = filters.DateFromToRangeFilter()

    def search_fields(self, queryset, name, value):
        return queryset.filter(Q(username__icontains=value) | Q(email__icontains=value))

    class Meta:
        model = User
        fields = ["search", "role", "created_at"]


class ApplicantFilter(BaseUserFilter):
    gender = filters.ChoiceFilter(
        choices=Gender.choices, field_name="applicant_profile__gender"
    )

    class Meta(BaseUserFilter.Meta):
        fields = BaseUserFilter.Meta.fields + ["gender"]


class RecruiterFilter(BaseUserFilter):
    company = filters.CharFilter(
        field_name="recruiter_profile__company__name", lookup_expr="icontains"
    )

    class Meta(BaseUserFilter.Meta):
        fields = BaseUserFilter.Meta.fields + ["company"]
