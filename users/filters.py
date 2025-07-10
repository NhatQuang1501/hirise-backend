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


class CompanyFilter(BaseUserFilter):
    name = filters.CharFilter(
        field_name="company_profile__name", lookup_expr="icontains"
    )
    industry = filters.CharFilter(
        field_name="company_profile__industries__name", lookup_expr="icontains"
    )
    location = filters.CharFilter(
        field_name="company_profile__locations__city", lookup_expr="icontains"
    )
    skill = filters.CharFilter(
        field_name="company_profile__skills__name", lookup_expr="icontains"
    )

    class Meta(BaseUserFilter.Meta):
        fields = BaseUserFilter.Meta.fields + ["name", "industry", "location", "skill"]
