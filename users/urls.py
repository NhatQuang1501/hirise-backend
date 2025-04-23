from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from users.views.user_views import *
from users.views.authentication_views import *


urlpatterns = [
    # User endpoints
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<str:id>/", UserDetailView.as_view(), name="user-detail"),
    path("users/profile/", ProfileUpdateView.as_view(), name="profile-update"),
    path("profiles/me/update/", ProfileUpdateView.as_view(), name="profile-update"),
    # Authentication Endpoints
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/verify-otp/", OTPVerifyView.as_view(), name="verify-otp"),
    path("auth/resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
