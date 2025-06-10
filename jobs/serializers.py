from rest_framework import serializers
from users.models import CompanyProfile
from jobs.models import (
    Job,
    Location,
    Industry,
    SkillTag,
    SavedJob,
    JobStatistics,
    CompanyStatistics,
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
    CompanyProfileSerializer,
)
from django.db import transaction
from django.utils import timezone


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "address", "country", "description"]
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


class CompanyProfileMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = ("name", "logo", "website")


class JobSerializer(serializers.ModelSerializer):
    company = CompanyProfileSerializer(read_only=True)
    company_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    saved_count = serializers.SerializerMethodField()
    locations = LocationSerializer(many=True, read_only=True)
    industries = IndustrySerializer(many=True, read_only=True)
    skills = SkillTagSerializer(many=True, read_only=True)
    city_display = serializers.SerializerMethodField()

    location_names = serializers.ListField(
        child=serializers.CharField(max_length=255), write_only=True, required=False
    )
    industry_names = serializers.ListField(
        child=serializers.CharField(max_length=100), write_only=True, required=False
    )
    skill_names = serializers.ListField(
        child=serializers.CharField(max_length=100), write_only=True, required=False
    )

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "company",
            "company_name",
            "description",
            "responsibilities",
            "requirements",
            "benefits",
            "status",
            "status_display",
            "job_type",
            "experience_level",
            "city",
            "city_display",
            "min_salary",
            "max_salary",
            "currency",
            "is_salary_negotiable",
            "salary_display",
            "closed_date",
            "locations",
            "industries",
            "skills",
            "location_names",
            "industry_names",
            "skill_names",
            "created_at",
            "updated_at",
            "is_saved",
            "saved_count",
        ]
        read_only_fields = [
            "id",
            "company",
            "company_name",
            "created_at",
            "updated_at",
            "status_display",
            "city_display",
            "salary_display",
            "is_saved",
            "saved_count",
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
            self.fields["company"] = CompanyProfileMiniSerializer(
                source="company.company_profile", read_only=True
            )

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_city_display(self, obj):
        return obj.get_city_display() if obj.city else None

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

    def get_saved_count(self, obj):
        # Đếm số lượng người đã lưu công việc này
        return obj.saved_by.count()

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
            required_fields = [
                "title",
                "description",
                "responsibilities",
                "requirements",
                "benefits",
                "job_type",
                "experience_level",
                "city",
            ]
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
            and request.user.role == Role.COMPANY
        ):
            # Lấy company profile
            company_profile = request.user.company_profile

            # Kiểm tra company profile tồn tại
            if not company_profile:
                raise serializers.ValidationError("Invalid company profile")

            # Tạo job với company
            validated_data["company"] = company_profile

            # Get location names
            location_names = validated_data.pop("location_names", [])
            # Get industry names
            industry_names = validated_data.pop("industry_names", [])
            # Get skill names
            skill_names = validated_data.pop("skill_names", [])

            # Create job
            job = super().create(validated_data)

            # Process locations
            if location_names:
                self._process_locations(job, location_names)

            # Process industries
            if industry_names:
                self._process_industries(job, industry_names)

            # Process skills
            if skill_names:
                self._process_skills(job, skill_names)

            # Create job statistics
            JobStatistics.objects.create(job=job)

            return job

        raise serializers.ValidationError("Only companies can create jobs")

    def update(self, instance, validated_data):
        # Cập nhật closed_date khi chuyển sang CLOSED
        if (
            validated_data.get("status") == JobStatus.CLOSED
            and instance.status != JobStatus.CLOSED
        ):
            validated_data["closed_date"] = timezone.now().date()

            # Từ chối các đơn ứng tuyển chưa xử lý
            self._reject_pending_applications(instance)

        # Get location names
        location_names = validated_data.pop("location_names", None)
        # Get industry names
        industry_names = validated_data.pop("industry_names", None)
        # Get skill names
        skill_names = validated_data.pop("skill_names", None)

        # Update job
        job = super().update(instance, validated_data)

        # Update m2m relationships
        if location_names is not None:
            self._process_locations(job, location_names)

        if industry_names is not None:
            self._process_industries(job, industry_names)

        if skill_names is not None:
            self._process_skills(job, skill_names)

        return job

    def _reject_pending_applications(self, job):
        """Reject all pending applications when job is closed"""
        with transaction.atomic():
            pending_applications = job.applications.filter(
                status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING]
            )
            pending_applications.update(
                status=ApplicationStatus.REJECTED,
                note="Job has been closed by the company",
            )

    def _process_locations(self, job, location_names):
        """Process location names and link them to job"""
        locations = []
        for location_name in location_names:
            if not location_name:
                continue
            # Tìm hoặc tạo location
            location, created = Location.objects.get_or_create(
                address=location_name.strip(), defaults={"country": "Vietnam"}
            )
            locations.append(location)

        # Xóa locations hiện tại và thêm locations mới
        job.locations.clear()
        if locations:
            job.locations.add(*locations)

    def _process_industries(self, job, industry_names):
        """Process industry names and link them to job"""
        industries = []
        for industry_name in industry_names:
            if not industry_name:
                continue
            # Tìm hoặc tạo industry
            industry, created = Industry.objects.get_or_create(
                name=industry_name.strip()
            )
            industries.append(industry)

        # Xóa industries hiện tại và thêm industries mới
        job.industries.clear()
        if industries:
            job.industries.add(*industries)

    def _process_skills(self, job, skill_names):
        """Process skill names and link them to job"""
        skills = []
        for skill_name in skill_names:
            if not skill_name:
                continue
            # Tìm hoặc tạo skill
            skill, created = SkillTag.objects.get_or_create(
                name=skill_name.strip(), defaults={"description": ""}
            )
            skills.append(skill)

        # Xóa skills hiện tại và thêm skills mới
        job.skills.clear()
        if skills:
            job.skills.add(*skills)


class SavedJobSerializer(serializers.ModelSerializer):
    job = JobSerializer(read_only=True)

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


class JobStatisticsSerializer(serializers.ModelSerializer):
    job_title = serializers.SerializerMethodField()

    class Meta:
        model = JobStatistics
        fields = [
            "id",
            "job",
            "job_title",
            "view_count",
            "accepted_count",
            "rejected_count",
            "average_processing_time",
        ]
        read_only_fields = ["id", "job", "job_title"]

    def get_job_title(self, obj):
        return obj.job.title if obj.job else None


class CompanyStatisticsSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = CompanyStatistics
        fields = [
            "id",
            "company",
            "company_name",
            "total_jobs",
            "active_jobs",
            "total_applications",
            "hired_applicants",
            "average_hire_rate",
        ]
        read_only_fields = ["id", "company", "company_name"]

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None
