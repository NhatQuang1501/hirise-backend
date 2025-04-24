from django.urls import path
from users.views.user_views import ApplicantView, RecruiterView
from users.views.authentication_views import *

urlpatterns = [
    # Users endpoints
    path("applicants/", ApplicantView.as_view(), name="applicant-list"),
    path("applicants/<uuid:pk>/", ApplicantView.as_view(), name="applicant-detail"),
    path("recruiters/", RecruiterView.as_view(), name="recruiter-list"),
    path("recruiters/<uuid:pk>/", RecruiterView.as_view(), name="recruiter-detail"),
    # Authentication endpoints
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/verify-otp/", OTPVerifyView.as_view(), name="verify-otp"),
    path("auth/resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("home/", HomeView.as_view(), name="home"),
]
