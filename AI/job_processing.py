# backend/AI/job_processing.py
import os
import re
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
from django.conf import settings
from .models import JobProcessedData

# Thiết lập logging
logger = logging.getLogger(__name__)

# Đường dẫn lưu trữ dữ liệu đã xử lý
JOB_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "job_processed_data")
os.makedirs(JOB_DATA_DIR, exist_ok=True)


class JobProcessor:
    """
    Lớp xử lý job data cho SBERT
    """

    def __init__(self, model_name="all-MiniLM-L6-v2"):
        # Khởi tạo SBERT model
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            logger.error(f"Lỗi khi khởi tạo SBERT model: {e}")
            self.model = None

    def clean_text(self, text):
        """
        Làm sạch văn bản
        """
        if not text:
            return ""

        # Loại bỏ các ký tự HTML
        text = re.sub(r"<.*?>", " ", text)

        # Chuẩn hóa xuống dòng thành khoảng trắng
        text = re.sub(r"\s*\n\s*", " ", text)

        # Chuẩn hóa dấu chấm câu (thêm khoảng trắng sau dấu chấm nếu chưa có)
        text = re.sub(r"\.(?=[A-Za-z])", ". ", text)

        # Loại bỏ khoảng trắng thừa
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def enhance_semantic_structure(self, text, section_name=""):
        """
        Tăng cường cấu trúc ngữ nghĩa của văn bản
        """
        if not text:
            return ""

        # Tách thành các điểm bullets nếu có
        if "•" in text or "*" in text or "-" in text:
            # Chuẩn hóa các ký tự bullet
            text = re.sub(r"(?:^|\n)[\s]*[•\*\-][\s]+", "\n• ", text)

            # Tách thành danh sách các điểm
            bullet_points = re.split(r"\n•\s+", text)
            bullet_points = [point.strip() for point in bullet_points if point.strip()]

            # Thêm ngữ cảnh từ tên section
            if section_name:
                context_prefix = f"{section_name}: "
                enhanced_points = []
                for point in bullet_points:
                    if not re.match(r"^[A-Z]", point):  # Nếu không bắt đầu bằng chữ hoa
                        point = point[0].upper() + point[1:] if point else ""
                    enhanced_points.append(f"{context_prefix}{point}")
                return " ".join(enhanced_points)
            else:
                return " ".join(bullet_points)

        # Nếu không có bullet, thêm ngữ cảnh từ tên section
        if section_name and not text.lower().startswith(section_name.lower()):
            return f"{section_name}: {text}"

        return text

    def extract_skills_from_text(self, text, skill_tags=None):
        """
        Trích xuất kỹ năng từ văn bản
        """
        if not text:
            return []

        # Nếu có danh sách skill_tags, sử dụng để tìm kiếm trong văn bản
        extracted_skills = []
        if skill_tags:
            for skill in skill_tags:
                if re.search(
                    r"\b" + re.escape(skill.name.lower()) + r"\b", text.lower()
                ):
                    extracted_skills.append(skill.name)

        return extracted_skills

    def process_job(self, job):
        """
        Xử lý job data và lưu trữ
        """
        try:
            # Lấy dữ liệu từ job
            title = job.title
            description = job.description
            responsibilities = job.responsibilities
            requirements = job.requirements
            preferred_skills = (
                job.preferred_skills
            )  # Lấy preferred_skills trực tiếp từ model
            experience_level = job.experience_level

            # Làm sạch văn bản
            clean_title = self.clean_text(title)
            clean_description = self.clean_text(description)
            clean_requirements = self.clean_text(requirements)
            clean_preferred_skills = self.clean_text(preferred_skills)
            clean_responsibilities = self.clean_text(responsibilities)

            # Tăng cường ngữ nghĩa
            enhanced_responsibilities = self.enhance_semantic_structure(
                clean_responsibilities, "Responsibilities"
            )
            enhanced_requirements = self.enhance_semantic_structure(
                clean_requirements, "Requirements"
            )
            enhanced_preferred = self.enhance_semantic_structure(
                clean_preferred_skills, "Preferred Skills"
            )

            # Lấy industry từ job
            industry_names = [industry.name for industry in job.industries.all()]
            industry_text = ", ".join(industry_names)

            # Lấy skills từ job
            skill_tags = job.skills.all()
            skill_names = [skill.name for skill in skill_tags]

            # Trích xuất thêm kỹ năng từ văn bản nếu cần
            extracted_skills = self.extract_skills_from_text(
                f"{description} {responsibilities} {requirements} {preferred_skills}",
                skill_tags,
            )

            # Kết hợp các kỹ năng và loại bỏ trùng lặp
            all_skills = list(set(skill_names + extracted_skills))

            # Kết hợp tất cả văn bản cho SBERT với cấu trúc tốt hơn
            combined_text = f"""
            Title: {clean_title}
            Experience Level: {experience_level}
            Industry: {industry_text}
            Skills: {', '.join(all_skills)}
            
            Job Description: {clean_description}
            
            {enhanced_responsibilities}
            
            {enhanced_requirements}
            
            {enhanced_preferred if enhanced_preferred else ""}
            """

            # Tạo hoặc cập nhật JobProcessedData
            job_data, created = JobProcessedData.objects.update_or_create(
                job=job,
                defaults={
                    "title": clean_title,
                    "description": clean_description,
                    "skills": all_skills,
                    "industry": industry_text,
                    "experience_level": experience_level,
                    "basic_requirements": clean_requirements,
                    "preferred_skills": clean_preferred_skills,
                    "responsibilities": clean_responsibilities,
                    "combined_text": combined_text,
                },
            )

            # Tạo embedding
            if self.model:
                # Tạo embedding
                embedding = self.model.encode(combined_text)

                # Lưu embedding vào file
                embedding_filename = f"job_{job.id}.npy"
                embedding_path = os.path.join(JOB_DATA_DIR, embedding_filename)
                np.save(embedding_path, embedding)

                # Cập nhật đường dẫn file
                job_data.embedding_file = embedding_filename
                job_data.save()

            return job_data

        except Exception as e:
            logger.error(f"Lỗi khi xử lý job {job.id}: {e}")
            return None


def process_job_on_publish(job):
    """
    Hàm được gọi khi job được publish
    """
    processor = JobProcessor()
    return processor.process_job(job)


def process_job_on_update(job):
    """
    Hàm được gọi khi job được cập nhật
    """
    processor = JobProcessor()
    return processor.process_job(job)
