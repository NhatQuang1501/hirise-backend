from django.contrib import admin
from jobs.models import *
from application.services import evaluate_applications_for_job


class LocationAdmin(admin.ModelAdmin):
    list_display = ("id", "address", "country")
    list_display_links = ("id",)
    list_editable = ["address"]
    search_fields = ("address", "country")


class IndustryAdmin(admin.ModelAdmin):
    list_editable = ["name"]
    list_display = ("id", "name")
    search_fields = ("name",)


class SkillTagAdmin(admin.ModelAdmin):
    list_editable = ["name"]
    list_display = ("id", "name", "description")
    search_fields = ("name", "description")


class JobAdmin(admin.ModelAdmin):
    list_editable = ["status", "is_salary_negotiable"]
    list_display = (
        "title",
        "company",
        "status",
        "job_type",
        "experience_level",
        "is_salary_negotiable",
        "created_at",
    )
    list_filter = ("status", "job_type", "experience_level")
    search_fields = ("title", "description", "company__name")
    date_hierarchy = "created_at"
    filter_horizontal = ("locations", "industries", "skills")
    actions = ["evaluate_applications"]

    def evaluate_applications(self, request, queryset):
        total_evaluated = 0
        for job in queryset:
            results = evaluate_applications_for_job(job.id)
            total_evaluated += len(results)

        if total_evaluated > 0:
            self.message_user(
                request,
                f"Evaluated {total_evaluated} applications for {queryset.count()} jobs",
            )
        else:
            self.message_user(request, "No applications to evaluate")

    evaluate_applications.short_description = "Evaluate applications for selected jobs"


class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("applicant", "job", "created_at")
    list_filter = ("created_at",)
    search_fields = ("applicant__user__username", "job__title")


class JobStatisticsAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "view_count",
        "application_count",
        "accepted_count",
        "rejected_count",
    )
    search_fields = ("job__title",)


class CompanyStatisticsAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "total_jobs",
        "active_jobs",
        "total_applications",
        "hired_applicants",
        "average_hire_rate",
    )
    search_fields = ("company__name",)


admin.site.register(Job, JobAdmin)
admin.site.register(Location, LocationAdmin)
admin.site.register(Industry, IndustryAdmin)
admin.site.register(SkillTag, SkillTagAdmin)
admin.site.register(SavedJob, SavedJobAdmin)
admin.site.register(JobStatistics, JobStatisticsAdmin)
admin.site.register(CompanyStatistics, CompanyStatisticsAdmin)
