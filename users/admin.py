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


admin.site.register(User, UserAdmin)
admin.site.register(ApplicantProfile, ApplicantProfileAdmin)
admin.site.register(CompanyProfile, CompanyProfileAdmin)
admin.site.register(SocialLink, SocialLinkAdmin)
