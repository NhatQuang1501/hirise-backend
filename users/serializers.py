from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db.models import Q
from django.db import transaction
from users.models import User, ApplicantProfile, RecruiterProfile, SocialLink
from users.choices import Role
from users.utils import get_otp_from_cache


# User Serializer đa năng với các trường linh hoạt
class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "is_verified",
            "is_locked",
            "created_at",
            "updated_at",
            "profile",
        ]
        read_only_fields = ["id", "role", "is_verified", "is_locked"]

    def __init__(self, *args, **kwargs):
        # Remove profile field if not needed
        exclude_profile = kwargs.pop("exclude_profile", False)
        super().__init__(*args, **kwargs)
        if exclude_profile:
            self.fields.pop("profile")

    # def get_profile(self, obj):
    #     if obj.role == Role.ADMIN:
    #         return None

    #     if obj.role == Role.APPLICANT:
    #         profile = ApplicantProfile.objects.filter(user=obj).first()
    #         if profile:
    #             return ApplicantProfileSerializer(profile).data

    #     if obj.role == Role.RECRUITER:
    #         profile = RecruiterProfile.objects.filter(user=obj).first()
    #         if profile:
    #             return RecruiterProfileSerializer(profile).data

    #     return None

    def get_profile(self, obj):
        if not self.context.get("exclude_profile", False):
            if obj.role == Role.APPLICANT:
                try:
                    profile = obj.applicant_profile
                    return ApplicantProfileSerializer(profile).data
                except ApplicantProfile.DoesNotExist:
                    return None

            elif obj.role == Role.RECRUITER:
                try:
                    profile = obj.recruiter_profile
                    return RecruiterProfileSerializer(profile).data
                except RecruiterProfile.DoesNotExist:
                    return None
        return None


# Serializers cho profiles
class SocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLink
        fields = ["id", "platform", "url", "custom_label"]
        read_only_fields = ["id"]


class ApplicantProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    social_links = SocialLinkSerializer(many=True, required=False)

    class Meta:
        model = ApplicantProfile
        fields = [
            "user",
            "full_name",
            "gender",
            "phone_number",
            "cv",
            "description",
            "social_links",
        ]

    def __init__(self, *args, **kwargs):
        # Tùy chỉnh trường user
        user_fields = kwargs.pop("user_fields", None)
        super().__init__(*args, **kwargs)

        if user_fields is not None and "user" in self.fields:
            self.fields["user"] = UserSerializer(read_only=True, fields=user_fields)

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related("user").prefetch_related("social_links")

    def update(self, instance, validated_data):
        social_links_data = validated_data.pop("social_links", None)

        # Cập nhật các trường của ApplicantProfile
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Cập nhật social links nếu có
        if social_links_data is not None:
            instance.social_links.all().delete()
            for link_data in social_links_data:
                SocialLink.objects.create(profile=instance, **link_data)

        return instance


class RecruiterProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    company_name = serializers.SerializerMethodField()
    company_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = RecruiterProfile
        fields = [
            "user",
            "full_name",
            "phone_number",
            "company",
            "company_name",
            "company_id",
        ]
        read_only_fields = ["company", "company_name"]

    def __init__(self, *args, **kwargs):
        # Tùy chỉnh trường user
        user_fields = kwargs.pop("user_fields", None)
        super().__init__(*args, **kwargs)

        if user_fields is not None and "user" in self.fields:
            self.fields["user"] = UserSerializer(read_only=True, fields=user_fields)

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related("user", "company")

    def validate_company_id(self, value):
        from jobs.models import Company

        if value and not Company.objects.filter(id=value).exists():
            raise serializers.ValidationError("Company does not exist")
        return value

    def update(self, instance, validated_data):
        company_id = validated_data.pop("company_id", None)

        if company_id:
            instance.company_id = company_id

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


# Các serializers xác thực
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(choices=Role.choices, required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "role"]

    def validate(self, data):
        """Gộp các validation thành một query duy nhất"""
        email = data.get("email")
        username = data.get("username")

        existing_user = (
            User.objects.filter(Q(email=email) | Q(username=username))
            .values_list("email", "username")
            .first()
        )

        if existing_user:
            errors = {}
            if email == existing_user[0]:
                errors["email"] = "Email has already been used"
            if username == existing_user[1]:
                errors["username"] = "Username has already been used"
            raise serializers.ValidationError(errors)

        return data

    def create(self, validated_data):

        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data["username"],
                email=validated_data["email"],
                password=validated_data["password"],
                role=validated_data["role"],
                is_verified=False,
            )

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
            user = (
                User.objects.filter(email=data["email"])
                .only("id", "email", "is_verified")
                .get()
            )
            if user.is_verified:
                raise serializers.ValidationError("Account was already verified")
            stored_otp = get_otp_from_cache(data["email"])

            if not stored_otp:
                raise serializers.ValidationError("OTP code has expired")

            if stored_otp != data["otp"]:
                raise serializers.ValidationError("Invalid OTP code")

            data["user"] = user
            return data
        except User.DoesNotExist:
            raise serializers.ValidationError("Email does not exist")


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email does not exist")
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])

        if not user:
            raise serializers.ValidationError("Username or password is incorrect")

        # Xác thực các điều kiện bổ sung
        errors = []
        if not user.is_verified:
            errors.append("Your account has not been verified")
        if user.is_locked:
            errors.append("Your account has been locked")

        if errors:
            raise serializers.ValidationError(", ".join(errors))

        data["user"] = user
        return data
