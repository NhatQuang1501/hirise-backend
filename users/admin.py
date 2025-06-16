from django.contrib import admin
from users.models import *


class UserAdmin(admin.ModelAdmin):
    list_editable = ["is_verified", "is_locked"]
    list_display = ["username", "role", "is_verified", "is_locked"]


class ApplicantProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "full_name"]


class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "name"]


class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ["user", "platform", "url"]


class CompanyFollowerAdmin(admin.ModelAdmin):
    list_display = ("applicant", "company", "created_at")
    list_filter = ("created_at",)
    search_fields = ("applicant__full_name", "company__name")
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        """Khi admin thêm follower, cập nhật follower_count"""
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        if is_new:
            obj.company.follower_count += 1
            obj.company.save(update_fields=["follower_count"])

    def delete_model(self, request, obj):
        """Khi admin xóa follower, cập nhật follower_count"""
        company = obj.company
        company.follower_count = max(0, company.follower_count - 1)
        company.save(update_fields=["follower_count"])
        super().delete_model(request, obj)


admin.site.register(User, UserAdmin)
admin.site.register(ApplicantProfile, ApplicantProfileAdmin)
admin.site.register(CompanyProfile, CompanyProfileAdmin)
admin.site.register(SocialLink, SocialLinkAdmin)
admin.site.register(CompanyFollower, CompanyFollowerAdmin)
