from django.contrib import admin
from .models import JobApplication, CVAnalysis, InterviewSchedule, TestFileUpload


class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("applicant", "cv_file", "job", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = (
        "applicant__user__username",
        "applicant__user__email",
        "job__title",
    )
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    raw_id_fields = ("applicant", "job")


class CVAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "match_score", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = (
        "application__applicant__user__username",
        "application__job__title",
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("application",)


class InterviewScheduleAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "scheduled_time", "meeting_link")
    list_filter = ("scheduled_time",)
    search_fields = (
        "application__applicant__user__username",
        "application__job__title",
    )
    raw_id_fields = ("application",)


class TestFileUploadAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "file", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("title",)
    readonly_fields = ("uploaded_at",)


admin.site.register(JobApplication, JobApplicationAdmin)
admin.site.register(InterviewSchedule, InterviewScheduleAdmin)
admin.site.register(CVAnalysis, CVAnalysisAdmin)
admin.site.register(TestFileUpload, TestFileUploadAdmin)
