# backend/AI/admin.py
from django.contrib import admin
from .models import JobProcessedData, CVProcessedData, JobCVMatch


@admin.register(JobProcessedData)
class JobProcessedDataAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "created_at", "updated_at")
    search_fields = ("job__title",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CVProcessedData)
class CVProcessedDataAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "created_at", "updated_at")
    search_fields = (
        "application__job__title",
        "application__applicant__user__username",
    )
    readonly_fields = ("id", "created_at", "updated_at")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("application__job", "application__applicant__user")
        )


@admin.register(JobCVMatch)
class JobCVMatchAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "application", "match_score", "created_at")
    search_fields = ("job__title", "application__applicant__full_name")
    list_filter = ("job",)
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-match_score",)
