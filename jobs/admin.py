from django.contrib import admin
from jobs.models import *


class LocationAdmin(admin.ModelAdmin):
    list_editable = ["city", "address"]
    list_display = ("city", "country", "address")
    search_fields = ("city", "country", "address")


class IndustryAdmin(admin.ModelAdmin):
    list_editable = ["name"]
    list_display = ("id", "name")
    search_fields = ("name",)


class SkillTagAdmin(admin.ModelAdmin):
    list_editable = ["name"]
    list_display = ("id", "name", "description")
    search_fields = ("name", "description")


class CompanyAdmin(admin.ModelAdmin):
    list_editable = ["name", "logo"]
    list_display = ("name", "email", "website", "founded_year")
    search_fields = ("name", "email", "description")
    filter_horizontal = ("locations", "industries", "skills")


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


class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("user", "job", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "job__title")


class JobApplicationAdmin(admin.ModelAdmin):
    list_editable = ["status"]
    list_display = ("applicant", "job", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("applicant__username", "job__title", "note")
    date_hierarchy = "created_at"


class JobViewAdmin(admin.ModelAdmin):
    list_display = ("job", "user", "viewed_at")
    list_filter = ("viewed_at",)
    search_fields = ("job__title", "user__username")
    date_hierarchy = "viewed_at"


admin.site.register(Job, JobAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(Location, LocationAdmin)
admin.site.register(Industry, IndustryAdmin)
admin.site.register(SkillTag, SkillTagAdmin)
admin.site.register(SavedJob, SavedJobAdmin)
admin.site.register(JobApplication, JobApplicationAdmin)
admin.site.register(JobView, JobViewAdmin)
