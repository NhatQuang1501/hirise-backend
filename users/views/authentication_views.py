from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

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
                    "message": "Register successfully. Kiểm tra email để lấy mã OTP, thực hiện xác thực email để sử dụng hệ thống.",
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
                    {"message": "Tài khoản đã được xác thực"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            create_and_send_otp(user)
            return Response(
                {
                    "message": "Mã xác thực mới đã được gửi đến email của bạn",
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
            user_data = UserSerializer(user).data

            profile_data = None
            if user.role == Role.APPLICANT:
                profile = ApplicantProfile.objects.filter(user=user).first()
                if profile:
                    profile_data = ApplicantProfileSerializer(profile).data
            elif user.role == Role.RECRUITER:
                profile = RecruiterProfile.objects.filter(user=user).first()
                if profile:
                    profile_data = RecruiterProfileSerializer(profile).data

            response_data = {
                "refresh": tokens["refresh"],
                "access": tokens["access"],
                "user": user_data,
            }

            if profile_data:
                response_data["profile"] = profile_data

            return Response(response_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success = token_blacklisted(refresh_token)
        if success:
            return Response(
                {"message": "Logout successfuly"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Cannot logout, invalid token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
