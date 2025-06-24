from rest_framework import serializers
from .models import JobApplication, CVAnalysis, InterviewSchedule, TestFileUpload
from users.serializers import ApplicantProfileSerializer
from jobs.serializers import JobSerializer
from users.choices import ApplicationStatus

# Thêm import này
try:
    from AI.cv_processing import process_cv_on_application
except ImportError:
    # Nếu module chưa được tạo, tạo hàm giả
    def process_cv_on_application(application):
        import logging

        logging.warning("AI.cv_processing module not found. CV processing skipped.")
        return None


class JobApplicationSerializer(serializers.ModelSerializer):
    applicant_profile = serializers.SerializerMethodField()
    job_details = serializers.SerializerMethodField()
    cv_filename = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = JobApplication
        fields = [
            "id",
            "job",
            "job_id",
            "applicant",
            "cv_file",
            "status",
            "status_display",
            "created_at",
            "updated_at",
            "applicant_profile",
            "job_details",
            "cv_filename",
            "company_id",
            "company_name",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "status_display",
            "company_id",
            "company_name",
        ]
        extra_kwargs = {
            "job": {"write_only": True},
            "applicant": {"write_only": True},
        }

    def get_job_details(self, obj):
        try:
            return {
                "id": obj.job.id,
                "title": obj.job.title,
                "company_name": (
                    obj.job.company.name if hasattr(obj.job, "company") else "Unknown"
                ),
                "company_logo": (
                    obj.job.company.logo.url
                    if hasattr(obj.job, "company") and obj.job.company.logo
                    else None
                ),
            }
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error getting job_details: {str(e)}")
            return {
                "id": str(obj.job.id) if hasattr(obj, "job") else None,
                "title": "Unknown",
                "company_name": "Unknown",
                "company_logo": None,
            }

    def get_cv_filename(self, obj):
        try:
            return obj.get_cv_filename()
        except Exception:
            return "unknown.pdf"

    def get_applicant_profile(self, obj):
        try:
            return {
                "id": obj.applicant.user.id if hasattr(obj.applicant, "user") else None,
                "username": (
                    obj.applicant.user.username
                    if hasattr(obj.applicant, "user")
                    else "unknown"
                ),
                "email": (
                    obj.applicant.user.email
                    if hasattr(obj.applicant, "user")
                    else "unknown@example.com"
                ),
                "full_name": (
                    obj.applicant.full_name
                    if hasattr(obj.applicant, "full_name")
                    else "Unknown"
                ),
                "phone_number": (
                    obj.applicant.phone_number
                    if hasattr(obj.applicant, "phone_number")
                    else ""
                ),
                "date_of_birth": (
                    obj.applicant.date_of_birth
                    if hasattr(obj.applicant, "date_of_birth")
                    else None
                ),
                "gender": (
                    obj.applicant.gender if hasattr(obj.applicant, "gender") else ""
                ),
                "description": (
                    obj.applicant.description
                    if hasattr(obj.applicant, "description")
                    else ""
                ),
            }
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error getting applicant_profile: {str(e)}")
            return {
                "id": None,
                "username": "unknown",
                "email": "unknown@example.com",
                "full_name": "Unknown",
                "phone_number": "",
                "date_of_birth": None,
                "gender": "",
                "description": "",
            }

    def get_status_display(self, obj):
        # Lấy label hiển thị của status từ ApplicationStatus
        for value, label in ApplicationStatus.choices:
            if value == obj.status:
                return label
        return obj.status

    def get_company_id(self, obj):
        return str(obj.job.company.user.id)

    def get_company_name(self, obj):
        return obj.job.company.name

    def validate(self, data):
        # Kiểm tra định dạng file CV
        cv_file = data.get("cv_file")
        if cv_file:
            file_name = cv_file.name.lower()
            if not (file_name.endswith(".pdf") or file_name.endswith(".docx")):
                raise serializers.ValidationError(
                    {"cv_file": "Only PDF and DOCX files are allowed."}
                )
        return data

    # Thêm phương thức create để xử lý CV sau khi tạo application
    def create(self, validated_data):
        # Tạo application
        application = super().create(validated_data)

        # Xử lý CV
        try:
            process_cv_on_application(application)
        except Exception as e:
            import logging

            logging.error(f"Error processing CV for application {application.id}: {e}")

        return application


class CVAnalysisSerializer(serializers.ModelSerializer):
    job_id = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    applicant_id = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()

    class Meta:
        model = CVAnalysis
        fields = [
            "id",
            "application",
            "extracted_content",
            "match_score",
            "created_at",
            "updated_at",
            "job_id",
            "job_title",
            "company_id",
            "company_name",
            "applicant_id",
            "applicant_name",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "job_id",
            "job_title",
            "company_id",
            "company_name",
            "applicant_id",
            "applicant_name",
        ]

    def get_job_id(self, obj):
        return str(obj.application.job.id)

    def get_job_title(self, obj):
        return obj.application.job.title

    def get_company_id(self, obj):
        return str(obj.application.job.company.user.id)

    def get_company_name(self, obj):
        return obj.application.job.company.name

    def get_applicant_id(self, obj):
        return str(obj.application.applicant.user.id)

    def get_applicant_name(self, obj):
        return obj.application.applicant.full_name


class JobApplicationListSerializer(serializers.ModelSerializer):
    applicant_profile = serializers.SerializerMethodField()
    cv_filename = serializers.SerializerMethodField()
    match_score = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    job_id = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = JobApplication
        fields = [
            "id",
            "applicant_profile",
            "cv_file",
            "cv_filename",
            "status",
            "status_display",
            "created_at",
            "match_score",
            "job_id",
            "job_title",
            "company_id",
            "company_name",
        ]

    def get_applicant_profile(self, obj):
        return {
            "id": obj.applicant.user.id,
            "username": obj.applicant.user.username,
            "email": obj.applicant.user.email,
            "full_name": obj.applicant.full_name,
            "phone_number": obj.applicant.phone_number,
            "date_of_birth": obj.applicant.date_of_birth,
            "gender": obj.applicant.gender,
            "description": obj.applicant.description,
        }

    def get_cv_filename(self, obj):
        return obj.get_cv_filename()

    def get_match_score(self, obj):
        try:
            return obj.cv_analysis.match_score
        except CVAnalysis.DoesNotExist:
            return None

    def get_status_display(self, obj):
        # Lấy label hiển thị của status từ ApplicationStatus
        for value, label in ApplicationStatus.choices:
            if value == obj.status:
                return label
        return obj.status

    def get_job_id(self, obj):
        return str(obj.job.id)

    def get_job_title(self, obj):
        return obj.job.title

    def get_company_id(self, obj):
        return str(obj.job.company.user.id)

    def get_company_name(self, obj):
        return obj.job.company.name


class InterviewScheduleSerializer(serializers.ModelSerializer):
    application_details = serializers.SerializerMethodField()
    job_id = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    applicant_id = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()

    class Meta:
        model = InterviewSchedule
        fields = [
            "id",
            "application",
            "application_details",
            "scheduled_time",
            "meeting_link",
            "note",
            "job_id",
            "job_title",
            "company_id",
            "company_name",
            "applicant_id",
            "applicant_name",
        ]
        read_only_fields = [
            "id",
            "application",
            "job_id",
            "job_title",
            "company_id",
            "company_name",
            "applicant_id",
            "applicant_name",
        ]

    def get_application_details(self, obj):
        return {
            "id": obj.application.id,
            "applicant_name": obj.application.applicant.full_name,
            "job_title": obj.application.job.title,
        }

    def get_job_id(self, obj):
        return str(obj.application.job.id)

    def get_job_title(self, obj):
        return obj.application.job.title

    def get_company_id(self, obj):
        return str(obj.application.job.company.user.id)

    def get_company_name(self, obj):
        return obj.application.job.company.name

    def get_applicant_id(self, obj):
        return str(obj.application.applicant.user.id)

    def get_applicant_name(self, obj):
        return obj.application.applicant.full_name


class TestFileUploadSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TestFileUpload
        fields = ["id", "title", "file", "file_name", "file_url", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at", "file_name", "file_url"]

    def get_file_name(self, obj):
        return obj.get_file_name()

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
