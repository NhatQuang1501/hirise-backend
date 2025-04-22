from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.exceptions import PermissionDenied

from .serializers import (
    UserSerializer,
    RegisterSerializer,
    OTPVerifySerializer,
    ResendOTPSerializer,
    LoginSerializer,
    ApplicantProfileSerializer,
    RecruiterProfileSerializer,
)
from .models import User, ApplicantProfile, RecruiterProfile
from .utils import (
    create_and_send_otp,
    delete_otp_from_cache,
    get_tokens_for_user,
    token_blacklisted,
)
from .choices import Role
from .permissions import IsOwnerOrAdmin, IsUserProfile


# --- User Views ---
class UserListView(generics.ListAPIView):
    """API để lấy danh sách users"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = User.objects.all()

        # Xử lý tìm kiếm và lọc
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) | Q(email__icontains=search)
            )

        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role=role)

        is_verified = self.request.query_params.get("is_verified")
        if is_verified is not None:
            is_verified = is_verified.lower() == "true"
            queryset = queryset.filter(is_verified=is_verified)

        return queryset


class UserDetailView(generics.RetrieveAPIView):
    """API để xem chi tiết một user"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    lookup_field = "id"


class UserUpdateView(generics.UpdateAPIView):
    """API để cập nhật thông tin user"""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_object(self):
        return self.request.user


class UserProfileView(APIView):
    """API để lấy thông tin profile của người dùng đang đăng nhập"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Lấy user data
        user = request.user
        user_data = UserSerializer(user).data

        # Lấy profile data dựa vào role
        profile_data = None
        if user.role == Role.APPLICANT:
            profile = get_object_or_404(
                ApplicantProfileSerializer.setup_eager_loading(
                    ApplicantProfile.objects.all()
                ),
                user=user,
            )
            profile_data = ApplicantProfileSerializer(profile).data
        elif user.role == Role.RECRUITER:
            profile = get_object_or_404(
                RecruiterProfileSerializer.setup_eager_loading(
                    RecruiterProfile.objects.all()
                ),
                user=user,
            )
            profile_data = RecruiterProfileSerializer(profile).data

        return Response({"user": user_data, "profile": profile_data})


# --- Profile Views ---
class ApplicantProfileDetailView(generics.RetrieveAPIView):
    """API để xem chi tiết profile ứng viên"""

    serializer_class = ApplicantProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = "user__id"

    def get_queryset(self):
        return ApplicantProfileSerializer.setup_eager_loading(
            ApplicantProfile.objects.all()
        )


class RecruiterProfileDetailView(generics.RetrieveAPIView):
    """API để xem chi tiết profile nhà tuyển dụng"""

    serializer_class = RecruiterProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = "user__id"

    def get_queryset(self):
        return RecruiterProfileSerializer.setup_eager_loading(
            RecruiterProfile.objects.all()
        )


class ProfileUpdateView(APIView):
    """API để cập nhật profile của người dùng đăng nhập"""

    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user

        if user.role == Role.APPLICANT:
            # Cập nhật profile ứng viên
            profile = get_object_or_404(ApplicantProfile, user=user)
            serializer = ApplicantProfileSerializer(
                profile, data=request.data, partial=True
            )
        elif user.role == Role.RECRUITER:
            # Cập nhật profile nhà tuyển dụng
            profile = get_object_or_404(RecruiterProfile, user=user)
            serializer = RecruiterProfileSerializer(
                profile, data=request.data, partial=True
            )
        else:
            return Response(
                {"error": "Không có profile cho loại người dùng này"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def put(self, request):
        # Xử lý tương tự patch nhưng yêu cầu đầy đủ trường
        return self.patch(request)


# --- Authentication Views ---
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
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

            # Xóa OTP và cập nhật trạng thái xác thực
            delete_otp_from_cache(user.email)
            user.is_verified = True
            user.save(update_fields=["is_verified"])

            # Chỉ thông báo xác thực thành công, không cấp token
            return Response(
                {
                    "message": "Xác thực thành công. Vui lòng đăng nhập với tài khoản của bạn.",
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
                {"error": "Refresh token là bắt buộc"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success = token_blacklisted(refresh_token)
        if success:
            return Response(
                {"message": "Đăng xuất thành công"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Không thể đăng xuất, token không hợp lệ"},
                status=status.HTTP_400_BAD_REQUEST,
            )
