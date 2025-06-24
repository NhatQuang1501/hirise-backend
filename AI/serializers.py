from rest_framework import serializers
from .models import JobProcessedData, CVProcessedData, JobCVMatch
from jobs.serializers import JobSerializer


class JobProcessedDataSerializer(serializers.ModelSerializer):
    job_title = serializers.SerializerMethodField()
    job_id = serializers.SerializerMethodField()

    class Meta:
        model = JobProcessedData
        fields = [
            "id",
            "job",
            "job_id",
            "job_title",
            "title",
            "description",
            "skills",
            "industry",
            "experience_level",
            "basic_requirements",
            "preferred_skills",
            "responsibilities",
            "combined_text",
            "embedding_file",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_job_title(self, obj):
        try:
            return obj.job.title if obj.job else None
        except Exception:
            return None

    def get_job_id(self, obj):
        try:
            return str(obj.job.id) if obj.job else None
        except Exception:
            return None


class JobProcessedDataDetailSerializer(JobProcessedDataSerializer):
    class Meta(JobProcessedDataSerializer.Meta):
        # Thêm các trường chi tiết nếu cần
        pass


class CVProcessedDataSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(
        source="application.applicant.full_name", read_only=True
    )
    applicant_id = serializers.UUIDField(
        source="application.applicant.user.id", read_only=True
    )
    job_title = serializers.CharField(source="application.job.title", read_only=True)
    job_id = serializers.UUIDField(source="application.job.id", read_only=True)
    company_name = serializers.CharField(
        source="application.job.company.name", read_only=True
    )

    class Meta:
        model = CVProcessedData
        fields = [
            "id",
            "application",
            "applicant_name",
            "applicant_id",
            "job_title",
            "job_id",
            "company_name",
            "summary",
            "experience",
            "education",
            "skills",
            "projects",
            "certifications",
            "languages",
            "achievements",
            "extracted_skills",
            "combined_text",
            "embedding_file",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CVProcessedDataDetailSerializer(CVProcessedDataSerializer):
    full_text = serializers.CharField(read_only=True)

    class Meta(CVProcessedDataSerializer.Meta):
        fields = CVProcessedDataSerializer.Meta.fields + ["full_text"]


class JobCVMatchSerializer(serializers.ModelSerializer):
    """
    Serializer cho model JobCVMatch
    """

    job_title = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()
    match_percentage = serializers.SerializerMethodField()

    class Meta:
        model = JobCVMatch
        fields = [
            "id",
            "job",
            "job_title",
            "application",
            "applicant_name",
            "match_score",
            "match_percentage",
            "detail_scores",
            "strengths",
            "weaknesses",
            "explanation",
            "created_at",
            "updated_at",
        ]

    def get_job_title(self, obj):
        return obj.job.title if obj.job else None

    def get_applicant_name(self, obj):
        if (
            obj.application
            and obj.application.applicant
            and obj.application.applicant.user
        ):
            return obj.application.applicant.user.username
        return None

    def get_match_percentage(self, obj):
        return int(obj.match_score * 100)
