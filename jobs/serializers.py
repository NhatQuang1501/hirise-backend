from rest_framework import serializers
from jobs.models import (
    Job,
    Company,
    Location,
    Industry,
    SkillTag,
    JobApplication,
    SavedJob,
)
from users.choices import (
    JobStatus,
    ApplicationStatus,
    JobType,
    ExperienceLevel,
    Currency,
)
from users.serializers import UserSerializer
from django.db import transaction
from django.utils import timezone


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
                "Minimum salary cannot be greater than maximum salary"
            )

        # Check status
        status = data.get("status", getattr(self.instance, "status", JobStatus.DRAFT))

        # Check closed_date
        closed_date = data.get("closed_date")
        if closed_date:
            today = timezone.now().date()
            if closed_date < today:
                raise serializers.ValidationError("Closing date cannot be in the past")

        # Validate required fields when publishing
        if status == JobStatus.PUBLISHED:
            required_fields = ["title", "description", "job_type", "experience_level"]
            for field in required_fields:
                field_value = data.get(field)
                if not field_value:
                    # If update, check current value
                    if self.instance:
                        field_value = getattr(self.instance, field, None)

                    if not field_value:
                        raise serializers.ValidationError(
                            f"Field '{field}' is required when publishing a job"
                        )

        # Handle when editing a published job
        if (
            self.instance
            and self.instance.status == JobStatus.PUBLISHED
            and not status == JobStatus.CLOSED
        ):
            # For PUT/PATCH requests, if status is not provided, job will return to DRAFT
            if not self.partial or "status" not in data:
                data["status"] = JobStatus.DRAFT

        # Cannot update closed job
        if self.instance and self.instance.status == JobStatus.CLOSED:
            raise serializers.ValidationError("Cannot update a closed job")

        return data

    def create(self, validated_data):
        # Tạo job với status đã được validate
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Cập nhật closed_date khi chuyển sang CLOSED
        if (
            validated_data.get("status") == JobStatus.CLOSED
            and instance.status != JobStatus.CLOSED
        ):
            validated_data["closed_date"] = timezone.now().date()

            # Từ chối các đơn ứng tuyển chưa xử lý
            self._reject_pending_applications(instance)

        # Đối với job published, nếu chỉnh sửa sẽ tự động chuyển về draft
        # (Đã xử lý ở validate)

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
