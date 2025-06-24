# backend/AI/job_processing.py
import os
import re
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
from django.conf import settings
from .models import JobProcessedData
import traceback

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
            logger.error(f"Error initializing SBERT model: {e}")
            self.model = None

        # Tải danh sách kỹ năng IT
        try:
            with open(os.path.join(settings.BASE_DIR, "AI", "it_skills.txt"), "r") as f:
                self.it_skills = [line.strip().lower() for line in f.readlines()]
        except Exception as e:
            logger.error(f"Error loading IT skills list: {e}")
            self.it_skills = []

    def clean_text(self, text):
        """
        Làm sạch văn bản cơ bản
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

    def advanced_preprocessing(self, text):
        """
        Tiền xử lý nâng cao cho văn bản IT
        """
        if not text:
            return ""

        # Chuẩn hóa cơ bản
        text = self.clean_text(text)

        # Xử lý từ viết tắt IT phổ biến
        abbreviations = {
            r"\bjs\b": "javascript",
            r"\bts\b": "typescript",
            r"\bpy\b": "python",
            r"\bml\b": "machine learning",
            r"\bai\b": "artificial intelligence",
            r"\boop\b": "object oriented programming",
            r"\bui\b": "user interface",
            r"\bux\b": "user experience",
            r"\bfe\b": "frontend",
            r"\bbe\b": "backend",
            r"\bfs\b": "fullstack",
            r"\bapi\b": "application programming interface",
            r"\bsql\b": "structured query language",
            r"\bnosql\b": "non-relational database",
            r"\bci\b": "continuous integration",
            r"\bcd\b": "continuous deployment",
            r"\bdb\b": "database",
            r"\bide\b": "integrated development environment",
            r"\boop\b": "object-oriented programming",
            r"\bfp\b": "functional programming",
            r"\bqa\b": "quality assurance",
            r"\bsdk\b": "software development kit",
            r"\bapi\b": "application programming interface",
            r"\bros\b": "robot operating system",
            r"\bos\b": "operating system",
            r"\bui/ux\b": "user interface and user experience",
        }

        for abbr, full in abbreviations.items():
            text = re.sub(abbr, full, text, flags=re.IGNORECASE)

        # Chuẩn hóa tên công nghệ
        tech_variants = {
            r"react\.?js": "react",
            r"node\.?js": "node",
            r"angular(?:js)?(?:\s*[0-9.]+)?": "angular",
            r"vue\.?js": "vue",
            r"express\.?js": "express",
            r"next\.?js": "nextjs",
            r"mongo\s*db": "mongodb",
            r"postgre(?:s|sql)": "postgresql",
            r"ms\s*sql": "mssql",
            r"my\s*sql": "mysql",
            r"type\s*script": "typescript",
            r"java\s*script": "javascript",
            r"dotnet": ".net",
            r"asp\.net(?:\s*core)?": "asp.net",
            r"laravel\s*[0-9.]*": "laravel",
            r"spring\s*boot": "spring boot",
            r"spring\s*framework": "spring",
            r"django\s*[0-9.]*": "django",
            r"flask\s*[0-9.]*": "flask",
            r"ruby\s*on\s*rails": "ruby on rails",
            r"tensorflow\s*[0-9.]*": "tensorflow",
            r"pytorch\s*[0-9.]*": "pytorch",
            r"kubernetes": "k8s",
            r"docker\s*compose": "docker-compose",
            r"github\s*actions": "github actions",
            r"gitlab\s*ci": "gitlab ci",
            r"jenkins\s*[0-9.]*": "jenkins",
        }

        for variant, standard in tech_variants.items():
            text = re.sub(variant, standard, text, flags=re.IGNORECASE)

        return text

    def enhance_semantic_structure(self, text, section_title):
        """
        Tăng cường cấu trúc ngữ nghĩa cho văn bản
        """
        if not text:
            return ""

        # Tiền xử lý nâng cao
        text = self.advanced_preprocessing(text)

        # Tách các điểm trong danh sách
        items = re.split(r"(?:\r?\n)|(?:•|\*|\-|\d+\.)\s*", text)
        items = [item.strip() for item in items if item.strip()]

        # Định dạng lại với cấu trúc rõ ràng
        formatted_text = f"{section_title}:\n"
        for i, item in enumerate(items, 1):
            formatted_text += f"• {item}\n"

        return formatted_text

    def extract_skills_from_text(self, text, skill_tags=None):
        """
        Trích xuất kỹ năng từ văn bản với cải tiến
        """
        if not text:
            return []

        # Áp dụng tiền xử lý nâng cao
        text = self.advanced_preprocessing(text.lower())

        extracted_skills = []

        # Tìm kiếm từ danh sách skill_tags (từ database)
        if skill_tags:
            for skill in skill_tags:
                if re.search(r"\b" + re.escape(skill.name.lower()) + r"\b", text):
                    extracted_skills.append(skill.name)

        # Tìm kiếm từ danh sách kỹ năng IT
        for skill in self.it_skills:
            if skill not in [s.lower() for s in extracted_skills] and re.search(
                r"\b" + re.escape(skill) + r"\b", text
            ):
                extracted_skills.append(skill)

        # Trích xuất kỹ năng với mức độ yêu cầu
        skill_levels = self.extract_skill_levels(text)

        # Kết hợp kết quả
        final_skills = []
        for skill in extracted_skills:
            if skill.lower() in skill_levels:
                final_skills.append(f"{skill} ({skill_levels[skill.lower()]})")
            else:
                final_skills.append(skill)

        return final_skills

    def extract_skill_levels(self, text):
        """
        Trích xuất kỹ năng cùng với mức độ yêu cầu
        """
        skill_levels = {}

        # Các mẫu để trích xuất kỹ năng với mức độ
        patterns = [
            # Pattern: "advanced knowledge of Python"
            (
                r"(beginner|basic|intermediate|advanced|expert|proficient|strong)\s+(knowledge|skills|experience|understanding|proficiency)\s+(?:of|in|with)\s+([a-zA-Z0-9\s\.\+\#]+)",
                lambda m: (m.group(3).strip().lower(), m.group(1).lower()),
            ),
            # Pattern: "Python (advanced level)"
            (
                r"([a-zA-Z0-9\s\.\+\#]+)\s*\(\s*(beginner|basic|intermediate|advanced|expert|proficient|strong)\s*(?:level|knowledge|skills|experience)?\s*\)",
                lambda m: (m.group(1).strip().lower(), m.group(2).lower()),
            ),
            # Pattern: "Python - advanced"
            (
                r"([a-zA-Z0-9\s\.\+\#]+)\s*[\-\:]\s*(beginner|basic|intermediate|advanced|expert|proficient|strong)",
                lambda m: (m.group(1).strip().lower(), m.group(2).lower()),
            ),
        ]

        for pattern, extract_func in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                skill, level = extract_func(match)
                # Chuẩn hóa mức độ
                if level in ["proficient", "strong"]:
                    level = "advanced"
                elif level == "basic":
                    level = "beginner"

                # Kiểm tra xem có phải kỹ năng IT không
                for it_skill in self.it_skills:
                    if it_skill in skill:
                        skill_levels[it_skill] = level
                        break

        return skill_levels

    def extract_experience_requirements(self, text):
        """
        Trích xuất yêu cầu kinh nghiệm từ văn bản job
        """
        experience_reqs = {}

        # Mẫu regex để tìm yêu cầu kinh nghiệm
        patterns = [
            r"(\d+)[\+]?\s*(?:years|yrs)(?:\s*of)?\s*(?:experience|exp)(?:\s*in|\s*with)?\s*([a-zA-Z0-9\s\.\+\#]+)",
            r"experience(?:\s*of|\s*in|\s*with)?\s*([a-zA-Z0-9\s\.\+\#]+)(?:\s*for)?\s*(\d+)[\+]?\s*(?:years|yrs)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if pattern.startswith(r"(\d+)"):
                    years = int(match.group(1))
                    tech = match.group(2).strip().lower()
                else:
                    tech = match.group(1).strip().lower()
                    years = int(match.group(2))

                # Chuẩn hóa tên công nghệ
                tech = self.normalize_technology_name(tech)

                # Lưu yêu cầu cao nhất nếu có nhiều yêu cầu cho cùng một công nghệ
                experience_reqs[tech] = max(experience_reqs.get(tech, 0), years)

        return experience_reqs

    def normalize_technology_name(self, tech_name):
        """
        Chuẩn hóa tên công nghệ
        """
        # Ánh xạ các biến thể tên công nghệ về dạng chuẩn
        tech_mapping = {
            "javascript": "javascript",
            "js": "javascript",
            "typescript": "typescript",
            "ts": "typescript",
            "react": "react",
            "reactjs": "react",
            "react.js": "react",
            "node": "node.js",
            "nodejs": "node.js",
            "node.js": "node.js",
            "angular": "angular",
            "angularjs": "angular",
            "vue": "vue.js",
            "vuejs": "vue.js",
            "vue.js": "vue.js",
            "python": "python",
            "django": "django",
            "flask": "flask",
            "java": "java",
            "spring": "spring",
            "spring boot": "spring boot",
            "c#": "c#",
            ".net": ".net",
            "dotnet": ".net",
            "asp.net": "asp.net",
            "php": "php",
            "laravel": "laravel",
            "ruby": "ruby",
            "ruby on rails": "ruby on rails",
            "rails": "ruby on rails",
            "go": "golang",
            "golang": "golang",
            "rust": "rust",
            "swift": "swift",
            "kotlin": "kotlin",
            "flutter": "flutter",
            "dart": "dart",
            "react native": "react native",
            "sql": "sql",
            "mysql": "mysql",
            "postgresql": "postgresql",
            "postgres": "postgresql",
            "mongodb": "mongodb",
            "mongo": "mongodb",
            "redis": "redis",
            "docker": "docker",
            "kubernetes": "kubernetes",
            "k8s": "kubernetes",
            "aws": "aws",
            "azure": "azure",
            "gcp": "gcp",
            "google cloud": "gcp",
            "devops": "devops",
            "ci/cd": "ci/cd",
            "git": "git",
            "github": "github",
            "gitlab": "gitlab",
            "jenkins": "jenkins",
            "jira": "jira",
            "agile": "agile",
            "scrum": "scrum",
            "machine learning": "machine learning",
            "ml": "machine learning",
            "artificial intelligence": "artificial intelligence",
            "ai": "artificial intelligence",
            "data science": "data science",
            "tensorflow": "tensorflow",
            "pytorch": "pytorch",
        }

        # Chuẩn hóa tên
        normalized = tech_name.lower().strip()

        # Áp dụng ánh xạ nếu có
        for key, value in tech_mapping.items():
            if key in normalized:
                return value

        return normalized

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
            preferred_skills = job.preferred_skills
            experience_level = job.experience_level

            # Áp dụng tiền xử lý nâng cao
            clean_title = self.advanced_preprocessing(title)
            clean_description = self.advanced_preprocessing(description)
            clean_requirements = self.advanced_preprocessing(requirements)
            clean_preferred_skills = self.advanced_preprocessing(preferred_skills)
            clean_responsibilities = self.advanced_preprocessing(responsibilities)

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

            # Trích xuất thêm kỹ năng từ văn bản
            extracted_skills = self.extract_skills_from_text(
                f"{description} {responsibilities} {requirements} {preferred_skills}",
                skill_tags,
            )

            # Trích xuất yêu cầu kinh nghiệm
            experience_requirements = self.extract_experience_requirements(
                f"{requirements} {preferred_skills}"
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
                    "experience_requirements": experience_requirements,
                },
            )

            # Tạo embedding
            if self.model:
                # Tạo embedding
                embedding = self.model.encode(combined_text)

                # Lưu embedding vào file
                embedding_filename = f"job_{job.id}.npy"
                embedding_path = os.path.join(JOB_DATA_DIR, embedding_filename)

                # Debug
                logger.info(f"Saving job embedding to: {embedding_path}")

                # Kiểm tra thư mục tồn tại
                os.makedirs(os.path.dirname(embedding_path), exist_ok=True)

                np.save(embedding_path, embedding)
                logger.info(f"Successfully saved job embedding for job {job.id}")

                # Cập nhật đường dẫn file
                job_data.embedding_file = embedding_filename
                job_data.save()
            else:
                logger.warning(
                    f"SBERT model not initialized, skipping embedding creation for job {job.id}"
                )

            return job_data

        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}")
            logger.error(traceback.format_exc())
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
