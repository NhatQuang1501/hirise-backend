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
    Role,
)
from users.serializers import (
    UserSerializer,
    ApplicantProfileSerializer,
    RecruiterProfileSerializer,
)
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
    recruiter = RecruiterProfileSerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    application_count = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "company",
            "recruiter",
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
            "recruiter",
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
        if (
            request
            and request.user.is_authenticated
            and request.user.role == Role.APPLICANT
        ):
            return SavedJob.objects.filter(
                applicant=request.user.applicant_profile, job=obj
            ).exists()
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
        request = self.context.get("request")
        if (
            request
            and request.user.is_authenticated
            and request.user.role == Role.RECRUITER
        ):
            # Lấy recruiter profile và company
            recruiter_profile = request.user.recruiter_profile
            company = recruiter_profile.company

            # Kiểm tra recruiter có thuộc company không
            if not company:
                raise serializers.ValidationError(
                    "Recruiter is not assigned to any company"
                )

            # Tạo job với company và recruiter
            validated_data["company"] = company
            validated_data["recruiter"] = recruiter_profile

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
        """Reject all pending applications when job is closed"""
        with transaction.atomic():
            pending_applications = job.applications.filter(
                status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING]
            )
            pending_applications.update(
                status=ApplicationStatus.REJECTED,
                note="Job has been closed by the recruiter",
            )


class JobApplicationSerializer(serializers.ModelSerializer):
    applicant = ApplicantProfileSerializer(read_only=True)
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

    def get_status_display(self, obj):
        return obj.get_status_display()

    def validate(self, data):
        # Kiểm tra người dùng có phải là applicant không
        request = self.context.get("request")
        if request.user.role != Role.APPLICANT:
            raise serializers.ValidationError("Only applicants can apply for jobs")

        # Kiểm tra job có ở trạng thái published không
        job = self.context.get("job")
        if job.status != JobStatus.PUBLISHED:
            raise serializers.ValidationError(
                "Cannot apply for a job that is not in published status"
            )

        return data

    def create(self, validated_data):
        request = self.context.get("request")
        job = self.context.get("job")

        # Tạo job application với applicant và job
        validated_data["applicant"] = request.user.applicant_profile
        validated_data["job"] = job

        return super().create(validated_data)


class SavedJobSerializer(serializers.ModelSerializer):
    job = JobSerializer(
        read_only=True,
        fields=[
            "id",
            "title",
            "company",
            "status",
            "min_salary",
            "max_salary",
            "currency",
        ],
        company_fields=["id", "name", "logo"],
    )

    class Meta:
        model = SavedJob
        fields = ["id", "job", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, data):
        # Kiểm tra người dùng có phải là applicant không
        request = self.context.get("request")
        if request.user.role != Role.APPLICANT:
            raise serializers.ValidationError("Only applicants can save jobs")

        # Kiểm tra job có tồn tại không
        job = self.context.get("job")
        if not job:
            raise serializers.ValidationError("Job does not exist")

        # Kiểm tra job đã được lưu chưa
        if SavedJob.objects.filter(
            applicant=request.user.applicant_profile, job=job
        ).exists():
            raise serializers.ValidationError("This job has already been saved")

        return data

    def create(self, validated_data):
        request = self.context.get("request")
        job = self.context.get("job")

        # Tạo saved job với applicant và job
        validated_data["applicant"] = request.user.applicant_profile
        validated_data["job"] = job

        return super().create(validated_data)
