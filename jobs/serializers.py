from rest_framework import serializers
from .models import Job, Company, Location, Industry, SkillTag, JobApplication
from users.choices import JobStatus, ApplicationStatus
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


class JobListSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    application_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "company",
            "status",
            "status_display",
            "job_type",
            "experience_level",
            "salary_display",
            "created_at",
            "updated_at",
            "application_count",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "status_display",
            "application_count",
        ]

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_application_count(self, obj):
        return obj.applications.count()


class JobDetailSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    application_count = serializers.SerializerMethodField()

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
        ]
        read_only_fields = [
            "id",
            "company",
            "created_at",
            "updated_at",
            "status_display",
            "salary_display",
            "application_count",
        ]

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_application_count(self, obj):
        return obj.applications.count()


class JobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            "id",
            "company",
            "title",
            "description",
            "responsibilities",
            "requirements",
            "benefits",
            "job_type",
            "experience_level",
            "min_salary",
            "max_salary",
            "currency",
            "is_salary_negotiable",
            "closed_date",
            "status",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        # Kiểm tra min_salary, max_salary
        min_salary = data.get("min_salary")
        max_salary = data.get("max_salary")

        if min_salary and max_salary and min_salary > max_salary:
            raise serializers.ValidationError(
                "Mức lương tối thiểu không thể lớn hơn mức lương tối đa"
            )

        # Kiểm tra status hợp lệ khi tạo
        status = data.get("status", JobStatus.DRAFT)
        if status not in [JobStatus.DRAFT, JobStatus.PUBLISHED]:
            raise serializers.ValidationError(
                f"Trạng thái không hợp lệ khi tạo job: {status}"
            )

        # Nếu status là PUBLISHED, cần kiểm tra các trường bắt buộc
        if status == JobStatus.PUBLISHED:
            required_fields = ["title", "description", "job_type", "experience_level"]
            missing_fields = [field for field in required_fields if not data.get(field)]

            if missing_fields:
                raise serializers.ValidationError(
                    f"Các trường sau là bắt buộc khi đăng job: {', '.join(missing_fields)}"
                )

        return data

    def create(self, validated_data):
        status = validated_data.get("status", JobStatus.DRAFT)

        # Mặc định là draft nếu không có status
        if not status:
            validated_data["status"] = JobStatus.DRAFT

        return super().create(validated_data)


class JobUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            "title",
            "description",
            "responsibilities",
            "requirements",
            "benefits",
            "job_type",
            "experience_level",
            "min_salary",
            "max_salary",
            "currency",
            "is_salary_negotiable",
            "closed_date",
            "status",
        ]

    def validate(self, data):
        # Kiểm tra min_salary, max_salary
        min_salary = data.get("min_salary", self.instance.min_salary)
        max_salary = data.get("max_salary", self.instance.max_salary)

        if min_salary and max_salary and min_salary > max_salary:
            raise serializers.ValidationError(
                "Mức lương tối thiểu không thể lớn hơn mức lương tối đa"
            )

        # Kiểm tra chuyển đổi status hợp lệ
        old_status = self.instance.status
        new_status = data.get("status", old_status)

        # Kiểm tra quy trình chuyển đổi status
        # Draft -> Published -> Closed
        if old_status != new_status:
            # Trường hợp chuyển từ CLOSED sang status khác
            if old_status == JobStatus.CLOSED:
                raise serializers.ValidationError(
                    "Không thể thay đổi trạng thái của job đã đóng"
                )

            # Trường hợp chuyển từ DRAFT sang PUBLISHED
            if old_status == JobStatus.DRAFT and new_status == JobStatus.PUBLISHED:
                # Kiểm tra các trường bắt buộc
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
                        value = getattr(self.instance, field)

                    if not value:
                        raise serializers.ValidationError(
                            f"Trường '{field}' là bắt buộc khi đăng job"
                        )

        return data

    def update(self, instance, validated_data):
        # Kiểm tra nếu job đang đóng, không cho phép cập nhật
        if instance.status == JobStatus.CLOSED:
            raise serializers.ValidationError("Không thể cập nhật job đã đóng")

        # Cập nhật closed_date khi chuyển sang CLOSED
        if (
            validated_data.get("status") == JobStatus.CLOSED
            and instance.status != JobStatus.CLOSED
        ):
            from django.utils import timezone

            validated_data["closed_date"] = timezone.now().date()

            # Cập nhật trạng thái các đơn ứng tuyển chưa xử lý
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
    job = JobListSerializer(read_only=True)

    class Meta:
        model = JobApplication
        fields = ["id", "applicant", "job", "created_at", "status", "note"]
        read_only_fields = ["id", "applicant", "job", "created_at"]

    def validate(self, data):
        # Các validation bổ sung có thể thêm ở đây
        return data


class JobApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobApplication
        fields = ["job", "note"]

    def validate_job(self, value):
        # Kiểm tra job có đang mở không
        if value.status != JobStatus.PUBLISHED:
            raise serializers.ValidationError(
                "Không thể ứng tuyển vào job này do đã đóng hoặc chưa đăng tải"
            )

        # Kiểm tra xem người dùng đã ứng tuyển job này chưa
        user = self.context["request"].user
        if JobApplication.objects.filter(applicant=user, job=value).exists():
            raise serializers.ValidationError("Bạn đã ứng tuyển vào job này rồi")

        return value

    def create(self, validated_data):
        # Lấy người dùng từ request
        user = self.context["request"].user
        validated_data["applicant"] = user
        validated_data["status"] = ApplicationStatus.PENDING

        return super().create(validated_data)


class JobApplicationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobApplication
        fields = ["status", "note"]

    def validate_status(self, value):
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
            ApplicationStatus.ACCEPTED: [],  # Không thể chuyển từ ACCEPTED sang trạng thái khác
            ApplicationStatus.REJECTED: [],  # Không thể chuyển từ REJECTED sang trạng thái khác
        }

        if value not in valid_transitions.get(current_status, []):
            valid_status = ", ".join(
                [
                    ApplicationStatus(s).label
                    for s in valid_transitions.get(current_status, [])
                ]
            )
            raise serializers.ValidationError(
                f"Không thể chuyển từ '{ApplicationStatus(current_status).label}' sang '{ApplicationStatus(value).label}'. "
                f"Trạng thái hợp lệ: {valid_status}"
            )

        return value

    def update(self, instance, validated_data):
        # Kiểm tra nếu job đã đóng, không cho phép cập nhật
        if (
            instance.job.status == JobStatus.CLOSED
            and validated_data.get("status") != ApplicationStatus.REJECTED
        ):
            raise serializers.ValidationError(
                "Không thể cập nhật đơn ứng tuyển cho job đã đóng"
            )

        return super().update(instance, validated_data)
