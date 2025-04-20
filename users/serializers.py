from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, ApplicantProfile, RecruiterProfile
from .enums import Role
from .utils import get_otp_from_cache


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(choices=Role.choices, required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "role"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email đã được sử dụng")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Tên đăng nhập đã được sử dụng")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data["role"],
            is_verified=False,
        )

        # Tạo profile dựa trên role
        if user.role == Role.APPLICANT:
            ApplicantProfile.objects.create(user=user)
        elif user.role == Role.RECRUITER:
            RecruiterProfile.objects.create(user=user)

        return user


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, max_length=6)

    def validate(self, data):
        try:
            user = User.objects.get(email=data["email"])
            stored_otp = get_otp_from_cache(data["email"])

            if not stored_otp:
                raise serializers.ValidationError(
                    "Mã OTP đã hết hạn hoặc không tồn tại"
                )

            if stored_otp != data["otp"]:
                raise serializers.ValidationError("Mã OTP không hợp lệ")

            data["user"] = user
            return data
        except User.DoesNotExist:
            raise serializers.ValidationError("Email không tồn tại")


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email không tồn tại")
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])

        if not user:
            raise serializers.ValidationError("Tên đăng nhập hoặc mật khẩu không đúng")

        if not user.is_verified:
            raise serializers.ValidationError("Tài khoản của bạn chưa được xác thực")

        if user.is_locked:
            raise serializers.ValidationError("Tài khoản của bạn đã bị khóa")

        data["user"] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "is_verified", "created_at"]
        read_only_fields = ["id", "is_verified", "created_at"]


class ApplicantProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ApplicantProfile
        fields = ["user", "full_name", "gender", "phone_number", "cv", "description"]


class RecruiterProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = RecruiterProfile
        fields = ["user", "full_name", "phone_number", "company"]
