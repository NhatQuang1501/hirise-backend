from django.contrib import admin
from jobs.models import *


class LocationAdmin(admin.ModelAdmin):
    list_editable = ["city", "address"]
    list_display = ["city", "country", "address", "description"]


class IndustryAdmin(admin.ModelAdmin):
    list_editable = ["name"]
    list_display = ["id", "name"]


class SkillTagAdmin(admin.ModelAdmin):
    list_editable = ["name"]
    list_display = ["id", "name"]


class CompanyAdmin(admin.ModelAdmin):
    list_editable = ["name", "logo"]
    list_display = ["email", "name", "logo"]


class JobAdmin(admin.ModelAdmin):
    list_editable = ["status", "is_salary_negotiable"]
    list_display = ["title", "company", "status", "is_salary_negotiable", "closed_date"]


class SavedJobAdmin(admin.ModelAdmin):
    list_display = ["job", "user", "created_at"]


class JobApplicationAdmin(admin.ModelAdmin):
    list_editable = ["status"]
    list_display = ["job", "applicant", "status", "created_at"]


admin.site.register(Location, LocationAdmin)
admin.site.register(Industry, IndustryAdmin)
admin.site.register(SkillTag, SkillTagAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(Job, JobAdmin)
admin.site.register(SavedJob, SavedJobAdmin)
admin.site.register(JobApplication, JobApplicationAdmin)
