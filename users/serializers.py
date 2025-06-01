from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db.models import Q
from django.db import transaction
from users.models import User, ApplicantProfile, CompanyProfile, SocialLink
from users.choices import Role
from users.utils import get_otp_from_cache


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
        read_only_fields = [
            "id",
            "role",
            "is_verified",
            "is_locked",
            "created_at",
            "updated_at",
        ]

    def get_profile(self, obj):
        if obj.role == Role.APPLICANT:
            try:
                profile = obj.applicant_profile
                return (
                    {
                        "full_name": profile.full_name,
                        "date_of_birth": profile.date_of_birth,
                        "gender": profile.gender,
                        "phone_number": profile.phone_number,
                        "cv": profile.cv.url if profile.cv else None,
                        "description": profile.description,
                    }
                    if profile
                    else None
                )
            except ApplicantProfile.DoesNotExist:
                return None

        elif obj.role == Role.COMPANY:
            try:
                profile = obj.company_profile
                return (
                    {
                        "name": profile.name,
                        "website": profile.website,
                        "logo": profile.logo.url if profile.logo else None,
                        "description": profile.description,
                        "benefits": profile.benefits,
                        "founded_year": profile.founded_year,
                        "locations": [loc.id for loc in profile.locations.all()],
                        "industries": [ind.id for ind in profile.industries.all()],
                        "skills": [skill.id for skill in profile.skills.all()],
                        "location_names": [
                            loc.address for loc in profile.locations.all()
                        ],
                        "industry_names": [
                            ind.name for ind in profile.industries.all()
                        ],
                        "skill_names": [skill.name for skill in profile.skills.all()],
                    }
                    if profile
                    else None
                )
            except CompanyProfile.DoesNotExist:
                return None
        return None

    # def __init__(self, *args, **kwargs):
    #     # Remove profile field if not needed
    #     exclude_profile = kwargs.pop("exclude_profile", False)
    #     super().__init__(*args, **kwargs)
    #     if exclude_profile:
    #         self.fields.pop("profile")


class UserWithProfileSerializer(UserSerializer):
    profile = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["profile"]

    def get_profile(self, obj):
        try:
            if obj.role == Role.APPLICANT:
                profile = getattr(obj, "applicant_profile", None)
                if profile:
                    return ApplicantProfileSerializer(
                        profile, context={"exclude_user": True}
                    ).data
            elif obj.role == Role.COMPANY:
                profile = getattr(obj, "company_profile", None)
                if profile:
                    return CompanyProfileSerializer(
                        profile, context={"exclude_user": True}
                    ).data
            return None
        except Exception as e:
            print(f"Profile serialization error: {str(e)}")  # Thêm log để debug
            return None


# Profile serializers
class SocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLink
        fields = ["id", "platform", "url", "custom_label"]
        read_only_fields = ["id"]


class ApplicantProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicantProfile
        fields = [
            "full_name",
            "date_of_birth",
            "gender",
            "phone_number",
            "cv",
            "description",
        ]

    def get_user(self, obj):
        if self.context.get("exclude_user", False):
            return None
        return UserSerializer(obj.user, context={"exclude_profile": True}).data

    def update(self, instance, validated_data):
        social_links_data = validated_data.pop("social_links", None)

        # Update ApplicantProfile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update social links if provided
        if social_links_data is not None:
            instance.social_links.all().delete()
            for link_data in social_links_data:
                SocialLink.objects.create(profile=instance, **link_data)

        return instance


class CompanyProfileSerializer(serializers.ModelSerializer):
    location_names = serializers.SerializerMethodField()
    industry_names = serializers.SerializerMethodField()
    skill_names = serializers.SerializerMethodField()
    logo = serializers.ImageField(required=False, allow_null=True)
    id = serializers.SerializerMethodField()

    class Meta:
        model = CompanyProfile
        fields = [
            "id",
            "name",
            "website",
            "logo",
            "description",
            "benefits",
            "founded_year",
            "locations",
            "industries",
            "skills",
            "location_names",
            "industry_names",
            "skill_names",
        ]

    def get_id(self, obj):
        # Trả về id của user làm id của company
        return obj.user.id if obj.user else None

    def get_user(self, obj):
        # Chỉ trả về user info khi context yêu cầu
        if not self.context.get("exclude_user", True):  # Mặc định sẽ exclude
            return UserSerializer(obj.user, context={"exclude_profile": True}).data
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Kiểm tra xem key "user" có tồn tại không trước khi truy cập
        if "user" in data and data["user"] is None:
            data.pop("user", None)
        return data

    def get_location_names(self, obj):
        return [loc.address for loc in obj.locations.all()]

    def get_industry_names(self, obj):
        return [industry.name for industry in obj.industries.all()]

    def get_skill_names(self, obj):
        return [skill.name for skill in obj.skills.all()]

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related("user").prefetch_related(
            "social_links", "locations", "industries", "skills"
        )

    def update(self, instance, validated_data):
        social_links_data = validated_data.pop("social_links", None)
        locations_data = validated_data.pop("locations", None)
        industries_data = validated_data.pop("industries", None)
        skills_data = validated_data.pop("skills", None)

        # Update CompanyProfile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update social links if provided
        if social_links_data is not None:
            instance.social_links.all().delete()
            for link_data in social_links_data:
                SocialLink.objects.create(user=instance.user, **link_data)

        # Update related entities if provided
        if locations_data is not None:
            instance.locations.set(locations_data)

        if industries_data is not None:
            instance.industries.set(industries_data)

        if skills_data is not None:
            instance.skills.set(skills_data)

        return instance


# Authentication serializers
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(choices=Role.choices, required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "role"]

    def validate(self, data):
        """Combine validations into a single query"""
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
            )

            # Tự động tạo profile tương ứng
            if user.role == Role.APPLICANT:
                ApplicantProfile.objects.create(user=user)
            elif user.role == Role.COMPANY:
                CompanyProfile.objects.create(user=user)

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
        username = data.get("username")
        password = data.get("password")

        if username and password:
            # Thử authenticate với username
            user = authenticate(username=username, password=password)

            # Nếu không thành công và username có dạng email
            if not user and "@" in username:
                try:
                    user_obj = User.objects.get(email=username)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass

            if not user:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "Unable to log in with provided credentials."
                        ]
                    }
                )

            if not user.is_verified:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "Account is not verified. Please verify your account."
                        ]
                    }
                )

            if user.is_locked:
                raise serializers.ValidationError(
                    {"non_field_errors": ["Account is locked."]}
                )

            data["user"] = user
            return data

        raise serializers.ValidationError(
            {"non_field_errors": ["Must include 'username' and 'password'."]}
        )
