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
    job_title = serializers.CharField(source="job.title", read_only=True)
    applicant_name = serializers.CharField(
        source="application.applicant.full_name", read_only=True
    )
    applicant_id = serializers.UUIDField(
        source="application.applicant.user.id", read_only=True
    )
    status = serializers.CharField(source="application.status", read_only=True)
    cv_file = serializers.FileField(source="application.cv_file", read_only=True)
    application_date = serializers.DateTimeField(
        source="application.created_at", read_only=True
    )
    analysis = serializers.SerializerMethodField()
    skills_match = serializers.SerializerMethodField()
    key_strengths = serializers.SerializerMethodField()
    areas_to_improve = serializers.SerializerMethodField()

    class Meta:
        model = JobCVMatch
        fields = [
            "id",
            "job",
            "job_title",
            "application",
            "applicant_name",
            "applicant_id",
            "match_score",
            "detailed_scores",
            "status",
            "cv_file",
            "application_date",
            "created_at",
            "updated_at",
            "analysis",
            "skills_match",
            "key_strengths",
            "areas_to_improve",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_analysis(self, obj):
        """Phân tích tổng quan về mức độ phù hợp"""
        scores = obj.detailed_scores

        if not scores:
            return "No detailed evaluation data."

        # Phân loại mức độ phù hợp
        match_level = (
            "high"
            if obj.match_score >= 60
            else "medium" if obj.match_score >= 40 else "low"
        )

        # Xác định điểm mạnh và điểm yếu
        strengths = []
        weaknesses = []

        for key, value in scores.items():
            score_percent = value * 100
            if score_percent >= 60:
                if key == "job_requirements_cv_skills":
                    strengths.append("Skills match job requirements")
                elif key == "job_requirements_cv_experience":
                    strengths.append("Experience matches job requirements")
                elif key == "job_skills_cv_skills":
                    strengths.append("Technical skills match job requirements")
                elif key == "job_responsibilities_cv_experience":
                    strengths.append("Experience matches job responsibilities")
            elif score_percent < 30:
                if key == "job_requirements_cv_skills":
                    weaknesses.append("Missing skills to match job requirements")
                elif key == "job_requirements_cv_experience":
                    weaknesses.append("Missing experience to match job requirements")
                elif key == "job_skills_cv_skills":
                    weaknesses.append("Missing technical skills")
                elif key == "job_responsibilities_cv_experience":
                    weaknesses.append("Experience does not match job responsibilities")

        analysis = f"Candidate has a {match_level} match with this job ({obj.match_score:.1f}%). "

        if strengths:
            analysis += f"Strengths: {', '.join(strengths)}. "

        if weaknesses:
            analysis += f"Areas to improve: {', '.join(weaknesses)}."

        return analysis

    def get_skills_match(self, obj):
        """Chi tiết về sự phù hợp của kỹ năng"""
        try:
            job_data = JobProcessedData.objects.get(job=obj.job)
            cv_data = CVProcessedData.objects.get(application=obj.application)

            job_skills = job_data.skills or []
            cv_skills = cv_data.extracted_skills or []

            # Tìm kỹ năng trùng khớp
            matching_skills = []
            for skill in job_skills:
                if any(cv_skill.lower() == skill.lower() for cv_skill in cv_skills):
                    matching_skills.append(skill)

            # Tìm kỹ năng còn thiếu
            missing_skills = []
            for skill in job_skills:
                if not any(cv_skill.lower() == skill.lower() for cv_skill in cv_skills):
                    missing_skills.append(skill)

            # Tính tỷ lệ khớp
            match_rate = (
                len(matching_skills) / len(job_skills) * 100 if job_skills else 0
            )

            result = {
                "match_rate": f"{match_rate:.1f}%",
                "matching_skills": matching_skills,
                "missing_skills": missing_skills,
                "total_job_skills": len(job_skills),
                "total_cv_skills": len(cv_skills),
            }

            return result
        except (JobProcessedData.DoesNotExist, CVProcessedData.DoesNotExist):
            return None

    def get_key_strengths(self, obj):
        """Xác định điểm mạnh chính của ứng viên"""
        scores = obj.detailed_scores
        if not scores:
            return []

        strengths = []

        # Xác định 3 điểm mạnh nhất
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        for key, value in sorted_scores:
            if value >= 0.3:  # Ngưỡng 30%
                if key == "job_requirements_cv_skills":
                    strengths.append("Skills match job requirements")
                elif key == "job_requirements_cv_experience":
                    strengths.append("Experience matches job requirements")
                elif key == "job_skills_cv_skills":
                    strengths.append("Technical skills match job requirements")
                elif key == "job_responsibilities_cv_experience":
                    strengths.append("Experience matches job responsibilities")
                elif key == "job_title_cv_summary":
                    strengths.append("Summary matches job title")

        return strengths

    def get_areas_to_improve(self, obj):
        """Identify areas that need improvement"""
        scores = obj.detailed_scores
        if not scores:
            return []

        improvements = []

        # Check if the candidate is a student/recent graduate
        try:
            cv_data = CVProcessedData.objects.get(application=obj.application)
            is_student = False

            # Check for student-related keywords in summary and education
            student_keywords = [
                "student",
                "studying",
                "recent graduate",
                "undergraduate",
                "graduate",
                "university",
                "college",
                "fresh graduate",
                "freshman",
                "sophomore",
                "final year student",
                "fourth year student",
                "third year student",
                "second year student",
                "first year student",
            ]
            if cv_data.summary:
                if any(
                    keyword in cv_data.summary.lower() for keyword in student_keywords
                ):
                    is_student = True
            if cv_data.education:
                if "present" in cv_data.education.lower() or any(
                    keyword in cv_data.education.lower() for keyword in student_keywords
                ):
                    is_student = True

            # If student with no experience but has projects
            if (
                is_student
                and not cv_data.experience.strip()
                and cv_data.projects.strip()
            ):
                # Skip weaknesses related to experience
                sorted_scores = sorted(scores.items(), key=lambda x: x[1])
                for key, value in sorted_scores:
                    if value < 0.3:  # 30% threshold
                        if key == "job_requirements_cv_skills":
                            improvements.append(
                                "Need to improve skills to match job requirements"
                            )
                        elif key == "job_skills_cv_skills":
                            improvements.append("Need to improve technical skills")
                        # Skip experience-related weaknesses
                        elif key == "job_title_cv_summary":
                            improvements.append("Summary does not match job title")

                # If no weaknesses were added but match score is low
                if not improvements and obj.match_score < 60:
                    improvements.append(
                        "Consider adding more relevant projects to showcase practical skills"
                    )

                return improvements[:3]  # Limit to 3 weaknesses
        except CVProcessedData.DoesNotExist:
            pass

        # Default processing if not a student or can't determine
        sorted_scores = sorted(scores.items(), key=lambda x: x[1])[:3]
        for key, value in sorted_scores:
            if value < 0.3:  # 30% threshold
                if key == "job_requirements_cv_skills":
                    improvements.append(
                        "Need to improve skills to match job requirements"
                    )
                elif key == "job_requirements_cv_experience":
                    improvements.append(
                        "Need to improve experience to match job requirements"
                    )
                elif key == "job_skills_cv_skills":
                    improvements.append("Need to improve technical skills")
                elif key == "job_responsibilities_cv_experience":
                    improvements.append(
                        "Experience does not match job responsibilities"
                    )
                elif key == "job_title_cv_summary":
                    improvements.append("Summary does not match job title")

        return improvements
