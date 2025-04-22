from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserListView,
    UserDetailView,
    UserUpdateView,
    UserProfileView,
    ApplicantProfileDetailView,
    RecruiterProfileDetailView,
    ProfileUpdateView,
    RegisterView,
    OTPVerifyView,
    ResendOTPView,
    LoginView,
    LogoutView,
)

urlpatterns = [
    # User Endpoints
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<uuid:id>/", UserDetailView.as_view(), name="user-detail"),
    path("users/me/update/", UserUpdateView.as_view(), name="user-update"),
    path("users/me/profile/", UserProfileView.as_view(), name="user-profile"),
    # Profile Endpoints
    path(
        "profiles/applicant/<uuid:user__id>/",
        ApplicantProfileDetailView.as_view(),
        name="applicant-profile-detail",
    ),
    path(
        "profiles/recruiter/<uuid:user__id>/",
        RecruiterProfileDetailView.as_view(),
        name="recruiter-profile-detail",
    ),
    path("profiles/me/update/", ProfileUpdateView.as_view(), name="profile-update"),
    # Authentication Endpoints
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/verify-otp/", OTPVerifyView.as_view(), name="verify-otp"),
    path("auth/resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
