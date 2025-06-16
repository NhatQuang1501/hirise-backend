from django.urls import path
from users.views.user_views import ApplicantView, CompanyView
from users.views.authentication_views import (
    RegisterView,
    OTPVerifyView,
    ResendOTPView,
    LoginView,
    LogoutView,
    OTPVerifyView,
    HomeView,
)
from users.views.user_views import (
    CompanyFollowerView,
    CheckFollowStatusView,
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Users endpoints
    path("applicants/", ApplicantView.as_view(), name="applicant-list"),
    path("applicants/<uuid:pk>/", ApplicantView.as_view(), name="applicant-detail"),
    path("companies/", CompanyView.as_view(), name="company-list"),
    path("companies/<uuid:pk>/", CompanyView.as_view(), name="company-detail"),
    # Company follower endpoints
    path("following/", CompanyFollowerView.as_view(), name="following-list"),
    path(
        "companies/<uuid:company_id>/follow/",
        CompanyFollowerView.as_view(),
        name="follow-company",
    ),
    path(
        "companies/<uuid:company_id>/check-follow/",
        CheckFollowStatusView.as_view(),
        name="check-follow-status",
    ),
    # Authentication endpoints
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/verify-otp/", OTPVerifyView.as_view(), name="verify-otp"),
    path("auth/resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("home/", HomeView.as_view(), name="home"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
