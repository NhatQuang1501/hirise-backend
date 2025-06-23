import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer, util
import logging
from django.conf import settings
from .models import JobProcessedData, CVProcessedData, JobCVMatch

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

        # Định nghĩa các trọng số cho từng phần
        self.section_weights = {
            # Trọng số cho việc so khớp giữa các phần
            "job_requirements_cv_skills": 0.25,  # Yêu cầu công việc và kỹ năng CV
            "job_requirements_cv_experience": 0.2,  # Yêu cầu công việc và kinh nghiệm CV
            "job_skills_cv_skills": 0.15,  # Kỹ năng công việc và kỹ năng CV
            "job_responsibilities_cv_experience": 0.15,  # Trách nhiệm công việc và kinh nghiệm CV
            "job_title_cv_summary": 0.1,  # Tiêu đề công việc và tóm tắt CV
            "job_preferred_cv_skills": 0.1,  # Kỹ năng ưu tiên và kỹ năng CV
            "combined_text": 0.05,  # Toàn bộ văn bản kết hợp
        }

        # Trọng số cho các kỹ năng khớp chính xác (exact match)
        self.exact_match_weight = 0.3  # 30% từ exact match, 70% từ semantic match

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

    def match_job_cv(self, job_id, cv_id=None, application_id=None):
        """
        So khớp một job với một CV cụ thể
        """
        try:
            job_data = JobProcessedData.objects.get(job_id=job_id)

            if cv_id:
                cv_data = CVProcessedData.objects.get(id=cv_id)
            elif application_id:
                cv_data = CVProcessedData.objects.get(application_id=application_id)
            else:
                return None

            # Tính toán điểm chi tiết
            detailed_scores = self.compute_detailed_matching_scores(job_data, cv_data)

            # Tính điểm tổng hợp
            weighted_score = self.compute_weighted_score(detailed_scores)

            # Lưu kết quả vào cơ sở dữ liệu
            match, created = JobCVMatch.objects.update_or_create(
                job=job_data.job,
                application=cv_data.application,
                defaults={
                    "match_score": weighted_score,
                    "detailed_scores": detailed_scores,
                },
            )

            return match

        except JobProcessedData.DoesNotExist:
            logger.error(f"JobProcessedData not found for job_id={job_id}")
            return None
        except CVProcessedData.DoesNotExist:
            logger.error(
                f"CVProcessedData not found for cv_id={cv_id} or application_id={application_id}"
            )
            return None
        except Exception as e:
            logger.error(f"Error matching job and CV: {e}")
            return None

    def match_job_with_all_applications(self, job_id):
        """
        So khớp một job với tất cả các CV đã apply cho job đó
        """
        try:
            job_data = JobProcessedData.objects.get(job_id=job_id)

            # Lấy tất cả CV đã apply cho job này
            cv_data_list = CVProcessedData.objects.filter(application__job_id=job_id)

            results = []
            for cv_data in cv_data_list:
                # Tính toán điểm chi tiết
                detailed_scores = self.compute_detailed_matching_scores(
                    job_data, cv_data
                )

                # Tính điểm tổng hợp
                weighted_score = self.compute_weighted_score(detailed_scores)

                # Lưu kết quả vào cơ sở dữ liệu
                match, created = JobCVMatch.objects.update_or_create(
                    job=job_data.job,
                    application=cv_data.application,
                    defaults={
                        "match_score": weighted_score,
                        "detailed_scores": detailed_scores,
                    },
                )

                results.append(match)

            # Sắp xếp kết quả theo điểm từ cao đến thấp
            results.sort(key=lambda x: x.match_score, reverse=True)

            return results

        except JobProcessedData.DoesNotExist:
            logger.error(f"JobProcessedData not found for job_id={job_id}")
            return []
        except Exception as e:
            logger.error(f"Error matching job with all CVs: {e}")
            return []
