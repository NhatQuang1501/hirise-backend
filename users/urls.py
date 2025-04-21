from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import *

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", OTPVerifyView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Profile route dựa trên role của người dùng
    path("profile/", ProfileView.as_view(), name="profile"),
    # Specific profile routes
    path(
        "profile/applicant/", ApplicantProfileView.as_view(), name="applicant-profile"
    ),
    path(
        "profile/recruiter/", RecruiterProfileView.as_view(), name="recruiter-profile"
    ),
]
