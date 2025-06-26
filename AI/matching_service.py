import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer, util
import logging
from django.conf import settings
from .models import JobProcessedData, CVProcessedData, JobCVMatch
import traceback
from jobs.models import Job
from application.models import JobApplication

logger = logging.getLogger(__name__)


class MatchingService:
    """
    Lớp dịch vụ xử lý việc so khớp giữa job và CV
    """

    def __init__(self, model_name="all-MiniLM-L6-v2"):
        # Khởi tạo SBERT model
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            logger.error(f"Error initializing SBERT model: {e}")
            self.model = None

        # Đường dẫn lưu trữ dữ liệu đã xử lý
        self.JOB_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "job_processed_data")
        self.CV_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "cv_processed_data")

        # Tải danh sách kỹ năng IT
        try:
            with open(os.path.join(settings.BASE_DIR, "AI", "it_skills.txt"), "r") as f:
                self.it_skills = [line.strip().lower() for line in f.readlines()]
        except Exception as e:
            logger.error(f"Error loading IT skills list: {e}")
            self.it_skills = []

        # Thêm các thuộc tính thiếu
        self.exact_match_weight = 0.3  # Trọng số cho việc khớp chính xác kỹ năng
        self.section_weights = {
            "job_requirements_cv_skills": 0.25,
            "job_requirements_cv_experience": 0.15,
            "job_skills_cv_skills": 0.20,
            "job_responsibilities_cv_experience": 0.15,
            "job_title_cv_summary": 0.10,
            "job_preferred_cv_skills": 0.10,
            "combined_text": 0.05,
        }

    def calculate_dynamic_weights(self, job_data, cv_data):
        """
        Tính toán trọng số động dựa trên đặc điểm dữ liệu
        """
        weights = {
            "job_requirements_cv_skills": 0.25,  # Trọng số mặc định
            "job_responsibilities_cv_experience": 0.20,
            "job_skills_cv_skills": 0.15,
            "job_title_cv_summary": 0.10,
            "job_preferred_cv_skills": 0.10,
            "combined_text": 0.05,
            "context_match": 0.15,  # Trọng số cho context-aware matching
        }

        # Điều chỉnh dựa trên độ chi tiết của job requirements
        if (
            job_data.basic_requirements
            and len(job_data.basic_requirements.split()) > 100
        ):
            # Job có yêu cầu chi tiết, tăng trọng số cho phần này
            weights["job_requirements_cv_skills"] += 0.05
            weights["combined_text"] -= 0.05

        # Điều chỉnh dựa trên số lượng kỹ năng trong CV
        if (
            hasattr(cv_data, "extracted_skills")
            and cv_data.extracted_skills
            and len(cv_data.extracted_skills) > 10
        ):
            # CV có nhiều kỹ năng, tăng trọng số cho phần này
            weights["job_skills_cv_skills"] += 0.05
            weights["job_title_cv_summary"] -= 0.05

        # Điều chỉnh dựa trên độ chi tiết của kinh nghiệm trong CV
        if cv_data.experience and len(cv_data.experience.split()) > 200:
            # CV có kinh nghiệm chi tiết, tăng trọng số cho phần này
            weights["job_responsibilities_cv_experience"] += 0.05
            weights["job_preferred_cv_skills"] -= 0.05

        # Điều chỉnh dựa trên sự có mặt của yêu cầu kinh nghiệm cụ thể
        if (
            hasattr(job_data, "experience_requirements")
            and job_data.experience_requirements
        ):
            # Job có yêu cầu kinh nghiệm cụ thể, tăng trọng số cho context matching
            weights["context_match"] += 0.05
            weights["combined_text"] -= 0.05

        # Chuẩn hóa trọng số để tổng = 1
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}

    def match_with_context(self, job_data, cv_data):
        """
        Thực hiện so khớp có nhận thức ngữ cảnh
        """
        context_scores = {}

        # 1. So khớp yêu cầu kinh nghiệm với kinh nghiệm ứng viên
        if (
            hasattr(job_data, "experience_requirements")
            and job_data.experience_requirements
        ):
            experience_requirements = job_data.experience_requirements
            candidate_experience = (
                cv_data.experience_details
                if hasattr(cv_data, "experience_details") and cv_data.experience_details
                else {}
            )

            for tech, required_years in experience_requirements.items():
                if tech in candidate_experience:
                    candidate_years = candidate_experience[tech]
                    # Tính điểm dựa trên tỷ lệ kinh nghiệm thực tế/yêu cầu
                    ratio = min(candidate_years / required_years, 1.5)  # Cap ở 150%
                    context_scores[f"experience_{tech}"] = ratio
                else:
                    context_scores[f"experience_{tech}"] = 0

        # 2. So khớp kỹ năng với mức độ ưu tiên
        # Xác định kỹ năng quan trọng từ job requirements
        important_skills = []
        if job_data.skills:
            important_skills = job_data.skills

        extracted_skills = []
        if hasattr(cv_data, "extracted_skills") and cv_data.extracted_skills:
            extracted_skills = [
                skill.split(" (")[0].lower() if " (" in skill else skill.lower()
                for skill in cv_data.extracted_skills
            ]

        for skill in important_skills:
            skill_lower = skill.lower()
            if skill_lower in extracted_skills:
                context_scores[f"skill_{skill_lower}"] = 1.0
            else:
                # Tìm kỹ năng tương tự
                for cv_skill in extracted_skills:
                    if skill_lower in cv_skill or cv_skill in skill_lower:
                        context_scores[f"skill_{skill_lower}"] = 0.7
                        break
                else:
                    context_scores[f"skill_{skill_lower}"] = 0

        # 3. Tính điểm trung bình có trọng số
        if context_scores:
            # Trọng số cao hơn cho các kỹ năng/kinh nghiệm quan trọng
            weighted_score = 0
            total_weight = 0

            for item, score in context_scores.items():
                if item.startswith("experience_"):
                    weight = 2.0  # Trọng số cao cho kinh nghiệm
                else:
                    weight = 1.0  # Trọng số chuẩn cho kỹ năng

                weighted_score += score * weight
                total_weight += weight

            return weighted_score / total_weight if total_weight > 0 else 0
        else:
            return 0

    def generate_match_explanation(self, job_data, cv_data, match_scores):
        """
        Tạo giải thích chi tiết về kết quả đánh giá
        """
        # Xác định điểm mạnh (kỹ năng khớp với yêu cầu)
        strengths = []

        # Xác định kỹ năng từ job và CV
        job_skills = job_data.skills if job_data.skills else []
        cv_skills = []
        if hasattr(cv_data, "extracted_skills") and cv_data.extracted_skills:
            cv_skills = [
                skill.split(" (")[0].lower() if " (" in skill else skill.lower()
                for skill in cv_data.extracted_skills
            ]

        # Tìm các kỹ năng khớp
        for skill in job_skills:
            skill_lower = skill.lower()
            if any(
                skill_lower in cv_skill or cv_skill in skill_lower
                for cv_skill in cv_skills
            ):
                strengths.append(f"Candidate has experience with {skill}")

        # Kiểm tra kinh nghiệm
        if (
            hasattr(job_data, "experience_requirements")
            and job_data.experience_requirements
        ):
            experience_reqs = job_data.experience_requirements
            candidate_exp = (
                cv_data.experience_details
                if hasattr(cv_data, "experience_details") and cv_data.experience_details
                else {}
            )

            for tech, required_years in experience_reqs.items():
                if tech in candidate_exp:
                    if candidate_exp[tech] >= required_years:
                        strengths.append(
                            f"Candidate has {candidate_exp[tech]} years of experience with {tech} (required: {required_years})"
                        )

        # Xác định điểm yếu (kỹ năng thiếu)
        weaknesses = []

        # Tìm các kỹ năng thiếu
        for skill in job_skills:
            skill_lower = skill.lower()
            if not any(
                skill_lower in cv_skill or cv_skill in skill_lower
                for cv_skill in cv_skills
            ):
                weaknesses.append(f"Job requires {skill} which was not found in the CV")

        # Kiểm tra kinh nghiệm thiếu
        if (
            hasattr(job_data, "experience_requirements")
            and job_data.experience_requirements
        ):
            experience_reqs = job_data.experience_requirements
            candidate_exp = (
                cv_data.experience_details
                if hasattr(cv_data, "experience_details") and cv_data.experience_details
                else {}
            )

            for tech, required_years in experience_reqs.items():
                if tech not in candidate_exp:
                    weaknesses.append(
                        f"Job requires {required_years} years of experience with {tech}"
                    )
                elif candidate_exp[tech] < required_years:
                    weaknesses.append(
                        f"Job requires {required_years} years of experience with {tech}, but candidate has only {candidate_exp[tech]} years"
                    )

        # Tạo giải thích tổng quan
        explanation = {
            "overall": f"The candidate's profile matches {int(match_scores.get('match_score', 0) * 100)}% of the job requirements.",
            "top_strengths": (
                strengths[:5] if strengths else ["No specific strengths identified"]
            ),
            "key_gaps": (
                weaknesses[:5] if weaknesses else ["No specific gaps identified"]
            ),
            "note": "This analysis is based on automated text processing and should be verified during interviews.",
        }

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "explanation": explanation,
        }

    def load_embedding(self, file_path):
        """
        Tải embedding từ file
        """
        try:
            if file_path.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            elif file_path.endswith(".npy"):
                return np.load(file_path)
            else:
                logger.error(f"File format not supported: {file_path}")
                return None
        except Exception as e:
            logger.error(f"Error loading embedding from file {file_path}: {e}")
            return None

    def compute_embedding(self, text):
        """
        Tính toán embedding cho văn bản
        """
        if self.model is None:
            return None

        try:
            return self.model.encode(text)
        except Exception as e:
            logger.error(f"Error computing embedding: {e}")
            return None

    def compute_similarity(self, text1, text2):
        """
        Tính toán độ tương đồng giữa hai văn bản
        """
        if self.model is None:
            return 0.0

        try:
            embedding1 = self.model.encode(text1)
            embedding2 = self.model.encode(text2)
            return float(util.cos_sim(embedding1, embedding2)[0][0])
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0

    def compute_similarity_from_embeddings(self, embedding1, embedding2):
        """
        Tính toán độ tương đồng từ hai embedding
        """
        try:
            if isinstance(embedding1, list):
                embedding1 = np.array(embedding1)
            if isinstance(embedding2, list):
                embedding2 = np.array(embedding2)

            return float(util.cos_sim(embedding1, embedding2)[0][0])
        except Exception as e:
            logger.error(f"Error computing similarity from embeddings: {e}")
            return 0.0

    def compute_exact_match_score(self, job_skills, cv_skills):
        """
        Tính điểm khớp chính xác giữa kỹ năng job và CV
        """
        if not job_skills or not cv_skills:
            return 0.0

        # Chuyển về lowercase để so sánh
        job_skills_lower = [skill.lower() for skill in job_skills]
        cv_skills_lower = [skill.lower() for skill in cv_skills]

        # Đếm số kỹ năng khớp
        matches = sum(1 for skill in job_skills_lower if skill in cv_skills_lower)

        # Tính tỷ lệ khớp so với tổng số kỹ năng yêu cầu
        if len(job_skills) > 0:
            return matches / len(job_skills)
        return 0.0

    def compute_detailed_matching_scores(self, job_data, cv_data):
        """
        Tính toán điểm số khớp chi tiết giữa job và CV
        """
        scores = {}

        # Tải embeddings nếu có
        job_embedding_path = os.path.join(self.JOB_DATA_DIR, job_data.embedding_file)
        job_embeddings = None
        if os.path.exists(job_embedding_path):
            job_embeddings = self.load_embedding(job_embedding_path)

        cv_embedding_path = os.path.join(self.CV_DATA_DIR, cv_data.embedding_file)
        cv_embeddings = None
        if os.path.exists(cv_embedding_path):
            cv_embeddings = self.load_embedding(cv_embedding_path)

        # So sánh từng phần theo các trọng số

        # 1. Yêu cầu công việc vs Kỹ năng CV
        scores["job_requirements_cv_skills"] = self.compute_similarity(
            job_data.basic_requirements, cv_data.skills
        )

        # 2. Yêu cầu công việc vs Kinh nghiệm CV
        combined_experience = cv_data.experience
        if not combined_experience.strip() and cv_data.projects:
            # If no experience but has projects, use projects instead
            combined_experience = cv_data.projects
        elif cv_data.projects:
            # If has both experience and projects, combine them
            combined_experience = f"{cv_data.experience}\n{cv_data.projects}"

        scores["job_requirements_cv_experience"] = self.compute_similarity(
            job_data.basic_requirements, combined_experience
        )

        # 3. Kỹ năng công việc vs Kỹ năng CV
        # Tính cả điểm ngữ nghĩa và khớp chính xác
        semantic_score = self.compute_similarity(
            ", ".join(job_data.skills) if job_data.skills else "", cv_data.skills
        )
        exact_match_score = self.compute_exact_match_score(
            job_data.skills, cv_data.extracted_skills
        )
        scores["job_skills_cv_skills"] = (
            1 - self.exact_match_weight
        ) * semantic_score + self.exact_match_weight * exact_match_score

        # 4. Trách nhiệm công việc vs Kinh nghiệm CV
        scores["job_responsibilities_cv_experience"] = self.compute_similarity(
            job_data.responsibilities, combined_experience
        )

        # 5. Tiêu đề công việc vs Tóm tắt CV
        scores["job_title_cv_summary"] = self.compute_similarity(
            job_data.title, cv_data.summary
        )

        # 6. Kỹ năng ưu tiên vs Kỹ năng CV
        scores["job_preferred_cv_skills"] = self.compute_similarity(
            job_data.preferred_skills, cv_data.skills
        )

        # 7. Toàn bộ văn bản kết hợp
        if job_embeddings is not None and cv_embeddings is not None:
            # Nếu có embeddings sẵn, sử dụng chúng
            if isinstance(cv_embeddings, dict) and "combined_text" in cv_embeddings:
                scores["combined_text"] = self.compute_similarity_from_embeddings(
                    job_embeddings, cv_embeddings["combined_text"]
                )
            else:
                scores["combined_text"] = self.compute_similarity(
                    job_data.combined_text, cv_data.combined_text
                )
        else:
            # Nếu không có embeddings, tính toán mới
            scores["combined_text"] = self.compute_similarity(
                job_data.combined_text, cv_data.combined_text
            )

        return scores

    def compute_weighted_score(self, detailed_scores):
        """
        Tính điểm tổng hợp dựa trên điểm chi tiết và trọng số
        """
        weighted_score = 0.0
        for section, score in detailed_scores.items():
            if section in self.section_weights:
                weighted_score += score * self.section_weights[section]

        # Chuyển về thang điểm 0-100
        return weighted_score * 100

    def match_job_cv(self, job_id, application_id=None, cv_id=None):
        """
        So khớp job và CV, trả về điểm số và phân tích
        """
        try:

            # Log để debug
            logger.info(
                f"Starting match_job_cv for job_id: {job_id}, application_id: {application_id}"
            )

            # Lấy job data
            try:
                job = Job.objects.get(id=job_id)
                job_data = JobProcessedData.objects.get(job=job)
                logger.info(f"Found job data for job_id: {job_id}")
            except (Job.DoesNotExist, JobProcessedData.DoesNotExist) as e:
                logger.error(
                    f"Job or job processed data not found for job_id: {job_id}. Error: {e}"
                )
                return None

            # Lấy CV data
            cv_data = None
            if application_id:
                try:
                    application = JobApplication.objects.get(id=application_id)
                    cv_data = CVProcessedData.objects.get(application=application)
                    logger.info(f"Found CV data for application_id: {application_id}")
                except (JobApplication.DoesNotExist, CVProcessedData.DoesNotExist) as e:
                    logger.error(
                        f"Application or CV processed data not found for application_id: {application_id}. Error: {e}"
                    )
                    return None

            if not cv_data:
                logger.error("No CV data available for matching")
                return None

            # Kiểm tra model đã được khởi tạo
            if self.model is None:
                logger.error("SentenceTransformer model is not initialized")
                return None

            # Tính toán trọng số động
            weights = self.calculate_dynamic_weights(job_data, cv_data)

            # Tính điểm khớp ngữ nghĩa cho từng phần
            semantic_scores = {}

            # So khớp job requirements với CV skills
            if job_data.basic_requirements and cv_data.skills:
                semantic_scores["job_requirements_cv_skills"] = self.compute_similarity(
                    job_data.basic_requirements, cv_data.skills
                )

            # So khớp job responsibilities với CV experience
            if job_data.responsibilities and cv_data.experience:
                semantic_scores["job_responsibilities_cv_experience"] = (
                    self.compute_similarity(
                        job_data.responsibilities, cv_data.experience
                    )
                )

            # So khớp job skills với CV skills
            if job_data.skills and cv_data.skills:
                semantic_scores["job_skills_cv_skills"] = self.compute_similarity(
                    ", ".join(job_data.skills), cv_data.skills
                )

            # So khớp job title với CV summary
            if job_data.title and cv_data.summary:
                semantic_scores["job_title_cv_summary"] = self.compute_similarity(
                    job_data.title, cv_data.summary
                )

            # So khớp job preferred skills với CV skills
            if job_data.preferred_skills and cv_data.skills:
                semantic_scores["job_preferred_cv_skills"] = self.compute_similarity(
                    job_data.preferred_skills, cv_data.skills
                )

            # So khớp combined text
            if job_data.combined_text and cv_data.combined_text:
                semantic_scores["combined_text"] = self.compute_similarity(
                    job_data.combined_text, cv_data.combined_text
                )

            # Thực hiện context-aware matching
            context_score = self.match_with_context(job_data, cv_data)
            semantic_scores["context_match"] = context_score

            # Tính điểm khớp chính xác cho kỹ năng
            exact_match_score = 0
            if (
                job_data.skills
                and hasattr(cv_data, "extracted_skills")
                and cv_data.extracted_skills
            ):
                exact_match_score = self.compute_exact_match_score(
                    job_data.skills, cv_data.extracted_skills
                )

            # Tính điểm tổng hợp với trọng số động
            weighted_score = 0
            for key, weight in weights.items():
                if key in semantic_scores:
                    weighted_score += semantic_scores[key] * weight

            # Kết hợp điểm semantic và exact match
            final_score = weighted_score * 0.7 + exact_match_score * 0.3

            # Chuẩn hóa điểm số để có phân phối tốt hơn
            # Áp dụng sigmoid để điểm số nằm trong khoảng 0-1 và có phân phối tốt hơn
            normalized_score = 1 / (1 + np.exp(-10 * (final_score - 0.5)))

            # Tạo giải thích về kết quả đánh giá
            match_scores = {
                "match_score": normalized_score,
                "semantic_score": weighted_score,
                "exact_match_score": exact_match_score,
                "detail_scores": semantic_scores,
            }

            match_analysis = self.generate_match_explanation(
                job_data, cv_data, match_scores
            )

            # Lưu kết quả vào database
            job_cv_match, created = JobCVMatch.objects.update_or_create(
                job=job,
                application=application if application_id else None,
                defaults={
                    "cv_processed_data": cv_data,
                    "match_score": normalized_score,
                    "detail_scores": semantic_scores,
                    "match_details": {},
                    "strengths": match_analysis["strengths"],
                    "weaknesses": match_analysis["weaknesses"],
                    "explanation": match_analysis["explanation"],
                },
            )

            return job_cv_match

        except Exception as e:
            logger.error(f"Error in match_job_cv: {e}")

            logger.error(traceback.format_exc())
            return None

    def match_job_with_all_applications(self, job_id):
        """
        Đánh giá độ phù hợp của job với tất cả application
        """
        try:

            # Lấy job
            try:
                job = Job.objects.get(id=job_id)
            except Job.DoesNotExist:
                logger.error(f"Job not found for job_id: {job_id}")
                return []

            # Lấy tất cả application cho job này
            applications = JobApplication.objects.filter(job=job)

            results = []
            for application in applications:
                # Thực hiện đánh giá độ phù hợp
                match_result = self.match_job_cv(job_id, application_id=application.id)
                if match_result:
                    results.append(match_result)

            return results

        except Exception as e:
            logger.error(f"Error in match_job_with_all_applications: {e}")

            logger.error(traceback.format_exc())
            return []
