from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import (
    GenericAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .serializers import (
    RegisterSerializer,
    OTPVerifySerializer,
    ResendOTPSerializer,
    LoginSerializer,
    UserSerializer,
    ApplicantProfileSerializer,
    RecruiterProfileSerializer,
    ApplicantProfileUpdateSerializer,
    RecruiterProfileUpdateSerializer,
)
from .models import User, ApplicantProfile, RecruiterProfile
from .utils import (
    create_and_send_otp,
    delete_otp_from_cache,
    get_tokens_for_user,
    token_blacklisted,
)
from .choices import Role


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
            # Xóa OTP và cập nhật trạng thái xác thực
            delete_otp_from_cache(user.email)
            user.is_verified = True
            user.save(update_fields=["is_verified"])

            # Tạo tokens và trả về response
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
            email = serializer.validated_data["email"]
            # Truy vấn tối ưu, chỉ lấy các trường cần thiết
            user = get_object_or_404(
                User.objects.only("id", "email", "username", "is_verified"), email=email
            )

            # Kiểm tra trạng thái xác thực
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
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success = token_blacklisted(refresh_token)
        if success:
            return Response(
                {"message": "Logout sucessfully"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Cannot logout, invalid token"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserProfileView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ApplicantProfileView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApplicantProfileSerializer

    def get_object(self):
        # Tối ưu truy vấn với eager loading
        queryset = ApplicantProfile.objects.all()
        queryset = self.get_serializer_class().setup_eager_loading(queryset)
        return get_object_or_404(queryset, user=self.request.user)


class RecruiterProfileView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RecruiterProfileSerializer

    def get_object(self):
        # Tối ưu truy vấn với eager loading
        queryset = RecruiterProfile.objects.all()
        queryset = self.get_serializer_class().setup_eager_loading(queryset)
        return get_object_or_404(queryset, user=self.request.user)


class ProfileMixin:
    """Mixin cung cấp phương thức chung cho các profile view"""

    def get_object(self):
        # Kiểm tra role và trả về profile tương ứng
        user = self.request.user
        if user.role == Role.APPLICANT:
            queryset = ApplicantProfile.objects.filter(user=user)
            queryset = ApplicantProfileSerializer.setup_eager_loading(queryset)
            return get_object_or_404(queryset)
        elif user.role == Role.RECRUITER:
            queryset = RecruiterProfile.objects.filter(user=user)
            queryset = RecruiterProfileSerializer.setup_eager_loading(queryset)
            return get_object_or_404(queryset)
        else:
            raise PermissionDenied("Không có quyền truy cập profile")


# class ProfileView(APIView):
#     """Trả về profile dựa trên role của người dùng"""

#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user

#         if user.role == Role.APPLICANT:
#             queryset = ApplicantProfile.objects.filter(user=user)
#             queryset = ApplicantProfileSerializer.setup_eager_loading(queryset)
#             profile = get_object_or_404(queryset)
#             serializer = ApplicantProfileSerializer(profile)
#         elif user.role == Role.RECRUITER:
#             queryset = RecruiterProfile.objects.filter(user=user)
#             queryset = RecruiterProfileSerializer.setup_eager_loading(queryset)
#             profile = get_object_or_404(queryset)
#             serializer = RecruiterProfileSerializer(profile)
#         else:
#             return Response(
#                 {"error": "Không có profile cho loại người dùng này"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )


#         return Response(serializer.data, status=status.HTTP_200_OK)
class ProfileView(APIView, ProfileMixin):
    """Trả về profile dựa trên role của người dùng"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = self.get_object()
            if request.user.role == Role.APPLICANT:
                serializer = ApplicantProfileSerializer(profile)
            else:  # RECRUITER
                serializer = RecruiterProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)


class ApplicantProfileView(RetrieveUpdateAPIView, ProfileMixin):
    """CRUD cho ApplicantProfile"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ApplicantProfileSerializer
        return ApplicantProfileUpdateSerializer

    # def get_object(self):
    #     # Kiểm tra role
    #     user = self.request.user
    #     if user.role != Role.APPLICANT:

    #         raise PermissionDenied("Bạn không phải là ứng viên")

    #     queryset = ApplicantProfile.objects.filter(user=user)
    #     if self.request.method == "GET":
    #         queryset = ApplicantProfileSerializer.setup_eager_loading(queryset)
    #     return get_object_or_404(queryset)
    def get_object(self):
        user = self.request.user
        if user.role != Role.APPLICANT:
            raise PermissionDenied("Bạn không phải là ứng viên")
        return super().get_object()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Lấy dữ liệu cập nhật với serializer đọc để trả về
        read_serializer = ApplicantProfileSerializer(instance)

        return Response(read_serializer.data)


class RecruiterProfileView(RetrieveUpdateAPIView):
    """CRUD cho RecruiterProfile"""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return RecruiterProfileSerializer
        return RecruiterProfileUpdateSerializer

    def get_object(self):
        # Kiểm tra role
        user = self.request.user
        if user.role != Role.RECRUITER:
            raise PermissionDenied("Bạn không phải là nhà tuyển dụng")

        queryset = RecruiterProfile.objects.filter(user=user)
        if self.request.method == "GET":
            queryset = RecruiterProfileSerializer.setup_eager_loading(queryset)
        return get_object_or_404(queryset)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Lấy dữ liệu cập nhật với serializer đọc để trả về
        read_serializer = RecruiterProfileSerializer(instance)

        return Response(read_serializer.data)
