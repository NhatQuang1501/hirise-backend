from django.contrib import admin
from jobs.models import *


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


class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("applicant", "job", "created_at")
    list_filter = ("created_at",)
    search_fields = ("applicant__user__username", "job__title")


class JobApplicationAdmin(admin.ModelAdmin):
    list_editable = ["status"]
    list_display = ("applicant", "job", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("applicant__user__username", "job__title", "note")
    date_hierarchy = "created_at"


class InterviewScheduleAdmin(admin.ModelAdmin):
    list_display = ("application", "scheduled_time")
    list_filter = ("scheduled_time",)
    search_fields = (
        "application__job__title",
        "application__applicant__user__username",
        "note",
    )


class CVReviewAdmin(admin.ModelAdmin):
    list_display = ("application", "match_score", "reviewed_at")
    list_filter = ("reviewed_at", "match_score")
    search_fields = (
        "application__job__title",
        "application__applicant__user__username",
        "summary",
    )


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
admin.site.register(JobApplication, JobApplicationAdmin)
admin.site.register(InterviewSchedule, InterviewScheduleAdmin)
admin.site.register(CVReview, CVReviewAdmin)
admin.site.register(JobStatistics, JobStatisticsAdmin)
admin.site.register(CompanyStatistics, CompanyStatisticsAdmin)
