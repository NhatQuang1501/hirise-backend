from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db import transaction
from users.serializers import (
    UserSerializer,
    RegisterSerializer,
    OTPVerifySerializer,
    ResendOTPSerializer,
    LoginSerializer,
    ApplicantProfileSerializer,
    RecruiterProfileSerializer,
)
from users.models import User, ApplicantProfile, RecruiterProfile
from users.utils import (
    create_and_send_otp,
    delete_otp_from_cache,
    get_tokens_for_user,
    token_blacklisted,
)
from users.choices import Role


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            create_and_send_otp(user)

            return Response(
                {
                    "message": "Register successfully. Please check your email to verify your account.",
                    "email": user.email,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]

            # Xóa OTP và cập nhật trạng thái xác thực
            try:
                with transaction.atomic():
                    delete_otp_from_cache(user.email)
                    user.is_verified = True
                    user.save(update_fields=["is_verified"])

                return Response(
                    {
                        "message": "Verify successfully. Please login with your new account.",
                        "email": user.email,
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response(
                    {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            user = get_object_or_404(
                User.objects.only("id", "email", "username", "is_verified"), email=email
            )

            if user.is_verified:
                return Response(
                    {"message": "Account already verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            create_and_send_otp(user)
            return Response(
                {
                    "message": "New OTP has been sent to your email. Please check your inbox.",
                    "email": email,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            tokens = get_tokens_for_user(user)

            # Lấy thông tin user và profile
            profile_data = self._get_user_profile(user)
            response_data = {
                "refresh": tokens["refresh"],
                "access": tokens["access"],
                "user": UserSerializer(user).data,
            }

            if profile_data:
                response_data["profile"] = profile_data

            return Response(response_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _get_user_profile(self, user):
        if user.role == Role.APPLICANT:
            profile = getattr(user, "applicant_profile", None)
            return ApplicantProfileSerializer(profile).data if profile else None
        elif user.role == Role.RECRUITER:
            profile = getattr(user, "recruiter_profile", None)
            return RecruiterProfileSerializer(profile).data if profile else None
        return None


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token_blacklisted(refresh_token)
            return Response(
                {"message": "Logout successfuly"}, status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {"error": "Cannot logout, invalid refresh token"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class HomeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "message": "Welcome to the Hirise API",
                "user": {
                    "username": request.user.username,
                    "email": request.user.email,
                    "role": request.user.role,
                },
            },
            status=status.HTTP_200_OK,
        )
