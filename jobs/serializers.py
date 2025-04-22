from rest_framework import serializers
from .models import Job, Company, Location, Industry, SkillTag, JobApplication, SavedJob
from users.choices import (
    JobStatus,
    ApplicationStatus,
    JobType,
    ExperienceLevel,
    Currency,
)
from users.serializers import UserSerializer
from django.db import transaction


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "city", "country", "address", "description"]
        read_only_fields = ["id"]


class IndustrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Industry
        fields = ["id", "name"]
        read_only_fields = ["id"]


class SkillTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillTag
        fields = ["id", "name", "description"]
        read_only_fields = ["id"]


class CompanySerializer(serializers.ModelSerializer):
    locations = LocationSerializer(many=True, read_only=True)
    industries = IndustrySerializer(many=True, read_only=True)
    skills = SkillTagSerializer(many=True, read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "email",
            "website",
            "logo",
            "description",
            "benefits",
            "founded_year",
            "locations",
            "industries",
            "skills",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def __init__(self, *args, **kwargs):
        fields = kwargs.pop("fields", None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class JobSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    application_count = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "company",
            "description",
            "responsibilities",
            "requirements",
            "benefits",
            "status",
            "status_display",
            "job_type",
            "experience_level",
            "min_salary",
            "max_salary",
            "currency",
            "is_salary_negotiable",
            "salary_display",
            "closed_date",
            "created_at",
            "updated_at",
            "application_count",
            "is_saved",
        ]
        read_only_fields = [
            "id",
            "company",
            "created_at",
            "updated_at",
            "status_display",
            "salary_display",
            "application_count",
            "is_saved",
        ]

    def __init__(self, *args, **kwargs):
        fields = kwargs.pop("fields", None)
        company_fields = kwargs.pop("company_fields", None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        if "company" in self.fields and company_fields is not None:
            self.fields["company"] = CompanySerializer(
                read_only=True, fields=company_fields
            )

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_application_count(self, obj):
        return obj.applications.count()

    def get_is_saved(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return SavedJob.objects.filter(user=request.user, job=obj).exists()
        return False

    def validate(self, data):
        # Validate min_salary & max_salary
        min_salary = data.get("min_salary", getattr(self.instance, "min_salary", None))
        max_salary = data.get("max_salary", getattr(self.instance, "max_salary", None))

        if min_salary and max_salary and min_salary > max_salary:
            raise serializers.ValidationError(
                "Mức lương tối thiểu không thể lớn hơn mức lương tối đa"
            )

        # Validate status transitions
        if self.instance and "status" in data:
            old_status = self.instance.status
            new_status = data["status"]

            # Không thể thay đổi job đã đóng
            if old_status == JobStatus.CLOSED and old_status != new_status:
                raise serializers.ValidationError(
                    "Không thể thay đổi trạng thái của job đã đóng"
                )

            # Validate required fields when publishing
            if new_status == JobStatus.PUBLISHED:
                required_fields = [
                    "title",
                    "description",
                    "job_type",
                    "experience_level",
                ]
                for field in required_fields:
                    if field in data:
                        value = data.get(field)
                    else:
                        value = getattr(self.instance, field, None)

                    if not value:
                        raise serializers.ValidationError(
                            f"Trường '{field}' là bắt buộc khi đăng job"
                        )

        return data

    def create(self, validated_data):
        # Đảm bảo mặc định là draft
        status = validated_data.get("status", JobStatus.DRAFT)
        if not status:
            validated_data["status"] = JobStatus.DRAFT

        # Company sẽ được gán trong view
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Không thể cập nhật job đã đóng
        if instance.status == JobStatus.CLOSED:
            raise serializers.ValidationError("Không thể cập nhật job đã đóng")

        # Cập nhật closed_date khi chuyển sang CLOSED
        if (
            validated_data.get("status") == JobStatus.CLOSED
            and instance.status != JobStatus.CLOSED
        ):
            from django.utils import timezone

            validated_data["closed_date"] = timezone.now().date()

            # Từ chối các đơn ứng tuyển chưa xử lý
            self._reject_pending_applications(instance)

        return super().update(instance, validated_data)

    def _reject_pending_applications(self, job):
        """Từ chối tất cả đơn ứng tuyển đang chờ xử lý khi job bị đóng"""
        with transaction.atomic():
            pending_applications = job.applications.filter(
                status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING]
            )
            pending_applications.update(
                status=ApplicationStatus.REJECTED,
                note="Job đã bị đóng bởi nhà tuyển dụng",
            )


class JobApplicationSerializer(serializers.ModelSerializer):
    applicant = UserSerializer(read_only=True)
    job = JobSerializer(read_only=True, fields=["id", "title", "company", "status"])
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = JobApplication
        fields = [
            "id",
            "applicant",
            "job",
            "created_at",
            "status",
            "status_display",
            "note",
        ]
        read_only_fields = ["id", "applicant", "job", "created_at", "status_display"]

    def __init__(self, *args, **kwargs):
        applicant_fields = kwargs.pop("applicant_fields", None)
        job_fields = kwargs.pop("job_fields", None)
        super().__init__(*args, **kwargs)

        if "applicant" in self.fields and applicant_fields is not None:
            self.fields["applicant"] = UserSerializer(
                read_only=True, fields=applicant_fields
            )

        if "job" in self.fields and job_fields is not None:
            self.fields["job"] = JobSerializer(read_only=True, fields=job_fields)

    def get_status_display(self, obj):
        return obj.get_status_display()

    def validate_status(self, value):
        """Kiểm tra chuyển đổi trạng thái hợp lệ"""
        if not self.instance:
            return value

        current_status = self.instance.status

        # Kiểm tra quy trình chuyển đổi status
        valid_transitions = {
            ApplicationStatus.PENDING: [
                ApplicationStatus.REVIEWING,
                ApplicationStatus.REJECTED,
            ],
            ApplicationStatus.REVIEWING: [
                ApplicationStatus.INTERVIEWED,
                ApplicationStatus.REJECTED,
            ],
            ApplicationStatus.INTERVIEWED: [
                ApplicationStatus.OFFERED,
                ApplicationStatus.REJECTED,
            ],
            ApplicationStatus.OFFERED: [
                ApplicationStatus.ACCEPTED,
                ApplicationStatus.REJECTED,
            ],
            ApplicationStatus.ACCEPTED: [],  # Không thể chuyển từ ACCEPTED
            ApplicationStatus.REJECTED: [],  # Không thể chuyển từ REJECTED
        }

        if value not in valid_transitions.get(current_status, []):
            valid_status = [
                ApplicationStatus(s).label
                for s in valid_transitions.get(current_status, [])
            ]
            valid_status_str = (
                ", ".join(valid_status)
                if valid_status
                else "không có trạng thái hợp lệ"
            )
            raise serializers.ValidationError(
                f"Không thể chuyển từ '{ApplicationStatus(current_status).label}' sang '{ApplicationStatus(value).label}'. "
                f"Trạng thái hợp lệ: {valid_status_str}"
            )

        return value


class SavedJobSerializer(serializers.ModelSerializer):
    job = JobSerializer(
        read_only=True,
        fields=[
            "id",
            "title",
            "company",
            "status",
            "job_type",
            "experience_level",
            "salary_display",
        ],
    )

    class Meta:
        model = SavedJob
        fields = ["id", "job", "created_at"]
        read_only_fields = ["id", "created_at"]
