from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import GenericAPIView
from .serializers import *
from .models import User
from .utils import (
    create_and_send_otp,
    delete_otp_from_cache,
    get_tokens_for_user,
    token_blacklisted,
)


class HomeView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        serializer = self.get_serializer(request.user)
        return Response(
            {
                "message": "Welcome to HiRise!",
                "user": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Tạo và gửi OTP
            create_and_send_otp(user)

            return Response(
                {
                    "message": "Đăng ký thành công. Kiểm tra email để lấy mã xác thực.",
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

            # Xóa OTP khỏi cache sau khi sử dụng
            delete_otp_from_cache(user.email)

            # Cập nhật trạng thái xác thực
            user.is_verified = True
            user.save(update_fields=["is_verified"])

            # Tạo tokens
            tokens = get_tokens_for_user(user)

            return Response(
                {
                    "message": "Xác thực thành công",
                    "refresh": tokens["refresh"],
                    "access": tokens["access"],
                    "user": UserSerializer(user).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.get(email=serializer.validated_data["email"])

            # Nếu người dùng đã xác thực
            if user.is_verified:
                return Response(
                    {"message": "Tài khoản đã được xác thực"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Tạo và gửi OTP mới
            create_and_send_otp(user)

            return Response(
                {
                    "message": "Mã xác thực mới đã được gửi đến email của bạn",
                    "email": user.email,
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

            return Response(
                {
                    "refresh": tokens["refresh"],
                    "access": tokens["access"],
                    "user": UserSerializer(user).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            token_blacklisted(refresh_token)

            return Response(
                {"message": "Đăng xuất thành công"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ApplicantProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ApplicantProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RecruiterProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = RecruiterProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
