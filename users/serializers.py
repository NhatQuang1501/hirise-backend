from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, ApplicantProfile, RecruiterProfile, SocialLink
from .choices import Role, Gender
from .utils import get_otp_from_cache
from django.db.models import Q, Prefetch
from jobs.models import Company
from django.db import transaction


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(choices=Role.choices, required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "role"]

    def validate(self, data):
        """Gộp các validation thành một query duy nhất"""
        email = data.get("email").lower()  # Chuẩn hóa email
        username = data.get("username")

        # Tối ưu truy vấn với một lần query
        existing_user = (
            User.objects.filter(Q(email=email) | Q(username=username))
            .values_list("email", "username")
            .first()
        )

        if existing_user:
            errors = {}
            if email == existing_user[0].lower():
                errors["email"] = "Email đã được sử dụng"
            if username == existing_user[1]:
                errors["username"] = "Tên đăng nhập đã được sử dụng"
            raise serializers.ValidationError(errors)

        # Chuẩn hóa dữ liệu
        data["email"] = email
        return data

    def create(self, validated_data):
        # Sử dụng transaction để đảm bảo tính nhất quán

        with transaction.atomic():
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
        email = data["email"].lower()

        try:
            # Chỉ lấy các trường cần thiết
            user = (
                User.objects.filter(email=email)
                .only("id", "email", "is_verified")
                .get()
            )
            stored_otp = get_otp_from_cache(email)

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
        email = value.lower()
        if not User.objects.filter(email=email).exists():
            raise serializers.ValidationError("Email không tồn tại")
        return email


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])

        if not user:
            raise serializers.ValidationError("Tên đăng nhập hoặc mật khẩu không đúng")

        # Xác thực các điều kiện bổ sung
        errors = []
        if not user.is_verified:
            errors.append("Tài khoản của bạn chưa được xác thực")
        if user.is_locked:
            errors.append("Tài khoản của bạn đã bị khóa")

        if errors:
            raise serializers.ValidationError(", ".join(errors))

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

    @staticmethod
    def setup_eager_loading(queryset):
        """Tối ưu truy vấn cho ApplicantProfile"""
        return queryset.select_related("user").only(
            "user__id",
            "user__username",
            "user__email",
            "user__role",
            "user__is_verified",
            "user__created_at",
            "full_name",
            "gender",
            "phone_number",
            "cv",
            "description",
        )


class RecruiterProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = RecruiterProfile
        fields = ["user", "full_name", "phone_number", "company"]

    @staticmethod
    def setup_eager_loading(queryset):
        """Tối ưu truy vấn cho RecruiterProfile"""
        return queryset.select_related("user", "company").only(
            "user__id",
            "user__username",
            "user__email",
            "user__role",
            "user__is_verified",
            "user__created_at",
            "full_name",
            "phone_number",
            "company__id",
            "company__name",
        )


class SocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLink
        fields = ["id", "platform", "url", "custom_label"]
        read_only_fields = ["id"]


class ApplicantProfileUpdateSerializer(serializers.ModelSerializer):
    social_links = SocialLinkSerializer(many=True, required=False)

    class Meta:
        model = ApplicantProfile
        fields = [
            "full_name",
            "gender",
            "phone_number",
            "cv",
            "description",
            "social_links",
        ]

    def validate_gender(self, value):
        if value and value not in [choice[0] for choice in Gender.choices]:
            raise serializers.ValidationError(
                f"Invalid gender. Please select: {', '.join([choice[1] for choice in Gender.choices])}"
            )
        return value

    def update(self, instance, validated_data):
        social_links_data = validated_data.pop("social_links", None)

        # Cập nhật các trường của ApplicantProfile
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Cập nhật social links nếu có
        if social_links_data is not None:
            # Xóa tất cả social links hiện tại
            instance.social_links.all().delete()

            # Tạo social links mới
            for link_data in social_links_data:
                SocialLink.objects.create(profile=instance, **link_data)

        return instance


class RecruiterProfileUpdateSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(required=False, write_only=True)

    class Meta:
        model = RecruiterProfile
        fields = ["full_name", "phone_number", "company_id"]

    def validate_company_id(self, value):
        if value and not Company.objects.filter(id=value).exists():
            raise serializers.ValidationError("Công ty không tồn tại")
        return value

    def update(self, instance, validated_data):
        company_id = validated_data.pop("company_id", None)

        # Cập nhật công ty nếu có
        if company_id:
            instance.company_id = company_id

        # Cập nhật các trường khác
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
