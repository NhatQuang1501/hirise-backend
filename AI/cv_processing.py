import os
import re
import json
import logging
import numpy as np
import fitz
import docx2txt
import spacy
import tempfile
import traceback
from sentence_transformers import SentenceTransformer
from django.conf import settings
from .models import CVProcessedData

# Thiết lập logging
logger = logging.getLogger(__name__)

# Đường dẫn lưu trữ dữ liệu CV đã xử lý
CV_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "cv_processed_data")
os.makedirs(CV_DATA_DIR, exist_ok=True)

# Tải mô hình ngôn ngữ spaCy
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("Đang cài đặt mô hình en_core_web_sm...")

    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")


class CVProcessor:
    """
    Lớp xử lý CV data cho SBERT
    """

    def __init__(self, model_name="all-MiniLM-L6-v2"):
        # Danh sách các mẫu tiêu đề cho từng phần thông tin
        self.section_patterns = {
            "summary": [
                "summary",
                "profile",
                "objective",
                "about me",
                "professional summary",
                "personal statement",
                "introduction",
                "overview",
                "career objective",
                "professional profile",
                "career summary",
                "about",
                "career profile",
                "bio",
            ],
            "experience": [
                "experience",
                "work experience",
                "employment",
                "work history",
                "professional experience",
                "career history",
                "employment history",
                "professional background",
                "work background",
                "career experience",
                "relevant experience",
                "job history",
                "professional career",
            ],
            "education": [
                "education",
                "academic",
                "qualifications",
                "educational background",
                "academic background",
                "academic qualifications",
                "educational qualifications",
                "academic history",
                "educational history",
                "academic achievements",
                "degrees",
                "academic record",
                "educational record",
                "studies",
            ],
            "skills": [
                "skills",
                "technical skills",
                "core competencies",
                "key skills",
                "professional skills",
                "tech stack",
                "technologies",
                "tech skills",
                "technical proficiency",
                "expertise",
                "competencies",
                "capabilities",
                "technical expertise",
                "skill set",
                "technical knowledge",
                "proficiencies",
                "technical capabilities",
                "technology skills",
                "areas of expertise",
                "technical competencies",
                "key competencies",
                "professional competencies",
                "specialized skills",
                "professional capabilities",
            ],
            "projects": [
                "projects",
                "personal projects",
                "academic projects",
                "portfolio",
                "project experience",
                "relevant projects",
                "key projects",
                "professional projects",
                "project work",
                "project portfolio",
                "featured projects",
                "major projects",
                "significant projects",
                "project highlights",
                "project achievements",
            ],
            "certifications": [
                "certifications",
                "certificates",
                "professional certifications",
                "accreditations",
                "credentials",
                "professional credentials",
                "qualifications",
                "professional qualifications",
                "licenses",
                "certified",
                "certification",
            ],
            "languages": [
                "languages",
                "language proficiency",
                "language skills",
                "foreign languages",
                "spoken languages",
                "language capabilities",
            ],
            "achievements": [
                "achievements",
                "accomplishments",
                "awards",
                "honors",
                "honors & awards",
                "recognitions",
                "accolades",
                "professional achievements",
                "career achievements",
                "notable achievements",
                "key achievements",
                "significant accomplishments",
                "distinctions",
            ],
        }

        # Từ điển để chuẩn hóa tên các phần
        self.section_mapping = {}
        for standard_name, variations in self.section_patterns.items():
            for variation in variations:
                self.section_mapping[variation.lower()] = standard_name

        # Khởi tạo SBERT model
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            logger.error(f"Lỗi khi khởi tạo SBERT model: {e}")
            self.model = None

    def extract_text_from_docx(self, docx_path):
        """
        Trích xuất nội dung văn bản từ file DOCX
        """
        try:
            text = docx2txt.process(docx_path)
            return text
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất văn bản từ file DOCX: {e}")
            return None

    def extract_text_from_pdf(self, pdf_path):
        """
        Trích xuất nội dung văn bản từ file PDF sử dụng PyMuPDF
        """
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                text += page_text + "\n\n"
            doc.close()
            return text
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất văn bản từ file PDF: {e}")
            return None

    def clean_text(self, text):
        """
        Làm sạch văn bản
        """
        if not text:
            return ""

        # Loại bỏ các ký tự đặc biệt không cần thiết nhưng giữ lại dấu chấm câu quan trọng
        text = re.sub(r"[^\w\s.,;:!?()•\-]", " ", text)

        # Chuẩn hóa xuống dòng
        text = re.sub(r"\n+", " ", text)

        # Chuẩn hóa dấu chấm câu
        text = re.sub(r"\.(?=[A-Za-z])", ". ", text)

        # Loại bỏ khoảng trắng thừa
        text = re.sub(r"\s+", " ", text).strip()

        # Loại bỏ các ký tự đặc biệt ở đầu và cuối
        text = text.strip(".,;:!?() ")

        return text

    def enhance_cv_section(self, text, section_name):
        """
        Tăng cường cấu trúc ngữ nghĩa của phần CV
        """
        if not text:
            return ""

        # Xử lý các mục bullet points
        if "•" in text or "*" in text or "-" in text:
            # Chuẩn hóa các ký tự bullet
            text = re.sub(r"(?:^|\n)[\s]*[•\*\-][\s]+", "\n• ", text)

            # Tách thành danh sách các điểm
            bullet_points = re.split(r"\n•\s+", text)
            bullet_points = [
                self.clean_text(point) for point in bullet_points if point.strip()
            ]

            # Thêm ngữ cảnh từ tên section
            enhanced_points = []
            for point in bullet_points:
                if point:
                    enhanced_points.append(f"{section_name} includes: {point}")

            return " ".join(enhanced_points)

        # Nếu là phần skills, chuẩn hóa thành danh sách
        if section_name.lower() == "skills":
            skills = re.split(r"[,\n]", text)
            skills = [skill.strip() for skill in skills if skill.strip()]
            return f"Skills include: {', '.join(skills)}"

        # Xử lý phần education
        if section_name.lower() == "education":
            # Trích xuất thông tin học vấn quan trọng
            degree_match = re.search(
                r"([A-Za-z\s]+(?:TECHNOLOGY|ENGINEERING|SCIENCE|BUSINESS|ARTS|DEGREE|DIPLOMA))",
                text,
                re.IGNORECASE,
            )
            school_match = re.search(
                r"(University|College|Institute|School)[\s\w]+", text, re.IGNORECASE
            )
            gpa_match = re.search(r"GPA:?\s*(\d+\.\d+)", text)

            edu_parts = []
            if degree_match:
                edu_parts.append(f"Degree in {degree_match.group(1)}")
            if school_match:
                edu_parts.append(f"from {school_match.group(0)}")
            if gpa_match:
                edu_parts.append(f"with GPA {gpa_match.group(1)}")

            if edu_parts:
                return f"Education: {' '.join(edu_parts)}"

        # Xử lý phần experience
        if section_name.lower() == "experience":
            # Trích xuất thông tin kinh nghiệm quan trọng
            position_match = re.search(
                r"(Developer|Engineer|Intern|Manager|Designer|Analyst|Consultant)\b",
                text,
                re.IGNORECASE,
            )
            company_match = re.search(r"at\s+([\w\s]+)", text, re.IGNORECASE)
            years_match = re.search(r"(\d+)\s*(?:year|yr)s?", text, re.IGNORECASE)

            exp_parts = []
            if position_match:
                exp_parts.append(f"Worked as {position_match.group(1)}")
            if company_match:
                exp_parts.append(f"at {company_match.group(1)}")
            if years_match:
                exp_parts.append(f"for {years_match.group(1)} years")

            if exp_parts:
                return f"Experience: {' '.join(exp_parts)}"

        # Xử lý phần achievements
        if section_name.lower() == "achievements":
            achievements = re.split(r"\n+", text)
            achievements = [ach.strip() for ach in achievements if ach.strip()]
            if achievements:
                return f"Achievements include: {'. '.join(achievements)}"

        # Mặc định thêm tên section
        return f"{section_name}: {self.clean_text(text)}"

    def extract_cv_content(self, file_path):
        """
        Trích xuất nội dung CV từ file DOCX hoặc PDF
        """
        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == ".docx":
            text = self.extract_text_from_docx(file_path)
        elif file_extension == ".pdf":
            text = self.extract_text_from_pdf(file_path)
        else:
            logger.error(f"Định dạng file không được hỗ trợ: {file_extension}")
            return None

        # Làm sạch văn bản
        processed_text = self.clean_text(text)
        return processed_text

    def identify_sections_by_headings(self, text):
        """
        Phát hiện các phần trong CV dựa trên tiêu đề
        """
        # Tạo pattern để tìm kiếm các tiêu đề section
        all_section_patterns = []
        for section, patterns in self.section_patterns.items():
            section_pattern = "|".join([re.escape(p) for p in patterns])
            all_section_patterns.append(f"({section_pattern})")

        combined_pattern = "|".join(all_section_patterns)

        # Tìm tất cả tiêu đề section trong văn bản (không phân biệt chữ hoa/thường)
        section_regex = re.compile(
            r"(?:^|\n)(?:\s*)((?:" + combined_pattern + r")(?:\s*:|\s*\n|\s*$))",
            re.IGNORECASE,
        )

        matches = list(section_regex.finditer(text))
        if not matches:
            return {"unknown": text}

        # Xác định vị trí bắt đầu của từng section
        sections = []
        for i, match in enumerate(matches):
            section_title = match.group(1).strip().lower().rstrip(":")

            # Chuẩn hóa tên section
            standard_section = self.get_standard_section_name(section_title)

            start_pos = match.start()
            end_pos = matches[i + 1].start() if i < len(matches) - 1 else len(text)

            # Trích xuất nội dung section (loại bỏ tiêu đề)
            content = text[match.end() : end_pos].strip()

            sections.append({"title": standard_section, "content": content})

        # Gộp các section cùng loại
        result = {}
        for section in sections:
            if section["title"] in result:
                result[section["title"]] += "\n" + section["content"]
            else:
                result[section["title"]] = section["content"]

        return result

    def get_standard_section_name(self, section_title):
        """
        Chuẩn hóa tên section dựa trên từ điển ánh xạ
        """
        # Loại bỏ dấu hai chấm và khoảng trắng
        clean_title = section_title.lower().strip().rstrip(":")

        # Kiểm tra từng từ khóa trong từ điển ánh xạ
        for keyword, standard_name in self.section_mapping.items():
            if keyword in clean_title:
                return standard_name

        # Nếu không tìm thấy, thử so sánh độ tương đồng
        return self.find_most_similar_section(clean_title)

    def find_most_similar_section(self, title):
        """
        Tìm section tương đồng nhất dựa trên độ tương đồng văn bản
        """
        # Tạo danh sách tất cả các pattern
        all_patterns = []
        for section, patterns in self.section_patterns.items():
            for pattern in patterns:
                all_patterns.append((section, pattern))

        # Nếu không có pattern nào, trả về unknown
        if not all_patterns:
            return "unknown"

        # Tính độ tương đồng
        max_similarity = 0
        best_section = "unknown"

        # Sử dụng spaCy để tính độ tương đồng
        try:
            title_doc = nlp(title)
            for section, pattern in all_patterns:
                pattern_doc = nlp(pattern)
                similarity = title_doc.similarity(pattern_doc)

                if (
                    similarity > max_similarity and similarity > 0.7
                ):  # Ngưỡng tương đồng
                    max_similarity = similarity
                    best_section = section
        except Exception as e:
            logger.error(f"Lỗi khi tính độ tương đồng: {e}")

        return best_section

    def extract_skills_from_text(self, text):
        """
        Trích xuất kỹ năng từ văn bản
        """
        if not text:
            return []

        # Tải danh sách kỹ năng từ file
        it_skills = []
        skills_file = os.path.join(settings.BASE_DIR, "AI", "it_skills.txt")

        try:
            if os.path.exists(skills_file):
                with open(skills_file, "r", encoding="utf-8") as f:
                    it_skills = [line.strip().lower() for line in f if line.strip()]
            else:
                # Ghi log nếu không tìm thấy file
                logger.warning(f"Không tìm thấy file kỹ năng: {skills_file}")
                # Tạo file trống nếu không tồn tại
                os.makedirs(os.path.dirname(skills_file), exist_ok=True)
                with open(skills_file, "w", encoding="utf-8") as f:
                    f.write("")
        except Exception as e:
            logger.error(f"Lỗi khi đọc file kỹ năng: {e}")

        # Chuẩn bị văn bản
        text_lower = text.lower()

        # Xử lý các định dạng khác nhau của văn bản
        lines = text.replace("\n", " \n ").split()

        # Tách theo các ký tự phân cách phổ biến
        words = []
        for line in lines:
            parts = re.split(r"[,;:\n]", line)
            words.extend([p.strip() for p in parts if p.strip()])

        # Tìm các kỹ năng trong văn bản
        found_skills = []

        # Kiểm tra các kỹ năng từ it_skills
        for skill in it_skills:
            if re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
                if skill not in found_skills:
                    found_skills.append(skill)

        # Tìm các công nghệ tiềm năng từ các từ riêng lẻ
        tech_keywords = []
        for word in words:
            word = word.strip(".,;:()[]{}")
            # Tìm từ viết hoa hoặc có định dạng đặc biệt (như .NET, Node.js)
            if re.match(r"^[A-Z][a-zA-Z0-9.]*(\.[a-zA-Z0-9]+)?$", word) or re.match(
                r"^[a-zA-Z0-9]+\.[a-zA-Z0-9]+$", word
            ):
                tech_keywords.append(word)

        # Thêm các từ khóa công nghệ tìm thấy
        for keyword in tech_keywords:
            if keyword.lower() not in [s.lower() for s in found_skills]:
                found_skills.append(keyword)

        # Kiểm tra các cụm từ đặc biệt
        special_patterns = [
            (r"\b[A-Z]+\b", []),  # Từ viết hoa hoàn toàn (ví dụ: HTML, CSS, PHP)
            (r"\b[A-Za-z]+\+\+\b", []),  # Ngôn ngữ như C++
            (r"\b[A-Za-z]+#\b", []),  # Ngôn ngữ như C#
            (r"\b[A-Za-z]+\.[A-Za-z]+\b", []),  # Công nghệ như ASP.NET, Node.js
        ]

        for pattern, _ in special_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match.lower() not in [s.lower() for s in found_skills]:
                    found_skills.append(match)

        # Chuẩn hóa danh sách kỹ năng tìm thấy
        final_skills = []
        for skill in found_skills:
            if len(skill) > 1:  # Loại bỏ các từ quá ngắn
                final_skills.append(skill)

        return list(set(final_skills))  # Loại bỏ trùng lặp

    def process_cv(self, application):
        """
        Xử lý CV data và lưu trữ
        """
        try:
            # Thay đổi cách truy cập file CV
            cv_file = application.cv_file

            # Kiểm tra loại file
            file_name = cv_file.name.lower()
            if file_name.endswith(".pdf"):
                # Tạo file tạm thời để xử lý PDF
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf", delete=False
                ) as temp_file:
                    # Đọc nội dung file từ storage và ghi vào file tạm thời
                    for chunk in cv_file.chunks():
                        temp_file.write(chunk)
                    temp_file_path = temp_file.name

                # Trích xuất nội dung từ file PDF tạm thời
                full_text = self.extract_text_from_pdf(temp_file_path)

                # Xóa file tạm thời sau khi sử dụng
                os.unlink(temp_file_path)

            elif file_name.endswith(".docx"):
                # Tạo file tạm thời để xử lý DOCX
                with tempfile.NamedTemporaryFile(
                    suffix=".docx", delete=False
                ) as temp_file:
                    # Đọc nội dung file từ storage và ghi vào file tạm thời
                    for chunk in cv_file.chunks():
                        temp_file.write(chunk)
                    temp_file_path = temp_file.name

                # Trích xuất nội dung từ file DOCX tạm thời
                full_text = self.extract_text_from_docx(temp_file_path)

                # Xóa file tạm thời sau khi sử dụng
                os.unlink(temp_file_path)

            else:
                logger.error(f"Định dạng file không được hỗ trợ: {file_name}")
                return None

            if not full_text:
                logger.error(f"Không thể trích xuất nội dung từ file CV: {file_name}")
                return None

            # Phân tích các phần trong CV
            sections = self.identify_sections_by_headings(full_text)

            # Trích xuất kỹ năng
            skills = []
            if "skills" in sections:
                skills = self.extract_skills_from_text(sections["skills"])
            else:
                # Nếu không có phần skills rõ ràng, tìm trong toàn bộ văn bản
                skills = self.extract_skills_from_text(full_text)

            # Làm sạch và tăng cường ngữ nghĩa cho từng phần
            enhanced_sections = {}
            for section_name, content in sections.items():
                if content:
                    enhanced_sections[section_name] = self.enhance_cv_section(
                        content, section_name.capitalize()
                    )

            # Tạo dữ liệu cấu trúc
            cv_data = {
                "summary": sections.get("summary", ""),
                "experience": sections.get("experience", ""),
                "education": sections.get("education", ""),
                "skills": sections.get("skills", ""),
                "projects": sections.get("projects", ""),
                "certifications": sections.get("certifications", ""),
                "languages": sections.get("languages", ""),
                "achievements": sections.get("achievements", ""),
                "extracted_skills": skills,
                "full_text": full_text,
            }

            # Kết hợp các phần quan trọng cho SBERT với cấu trúc tốt hơn
            important_sections = [
                "summary",
                "experience",
                "education",
                "skills",
                "projects",
                "achievements",
            ]

            combined_text_parts = []

            # Thêm thông tin về kỹ năng trước tiên vì đây là phần quan trọng nhất
            if skills:
                combined_text_parts.append(
                    f"Candidate has skills in: {', '.join(skills)}"
                )

            # Thêm các phần đã được tăng cường ngữ nghĩa
            for section in important_sections:
                if section in enhanced_sections and enhanced_sections[section]:
                    combined_text_parts.append(enhanced_sections[section])

            combined_text = " ".join(combined_text_parts)

            if not combined_text:
                combined_text = self.clean_text(full_text)

            # Tạo hoặc cập nhật CVProcessedData
            cv_processed_data, created = CVProcessedData.objects.update_or_create(
                application=application,
                defaults={
                    "summary": cv_data["summary"],
                    "experience": cv_data["experience"],
                    "education": cv_data["education"],
                    "skills": cv_data["skills"],
                    "projects": cv_data["projects"],
                    "certifications": cv_data["certifications"],
                    "languages": cv_data["languages"],
                    "achievements": cv_data["achievements"],
                    "extracted_skills": cv_data["extracted_skills"],
                    "full_text": cv_data["full_text"],
                    "combined_text": combined_text,
                },
            )

            # Tạo embedding nếu model đã được khởi tạo
            if self.model:
                # Tạo embedding cho toàn bộ văn bản
                full_text_embedding = self.model.encode(full_text)

                # Tạo embedding cho văn bản kết hợp
                combined_text_embedding = self.model.encode(combined_text)

                # Tạo embedding cho từng phần nếu có
                section_embeddings = {}
                for section in important_sections:
                    if section in cv_data and cv_data[section]:
                        section_embeddings[section] = self.model.encode(
                            cv_data[section]
                        )

                # Lưu các embedding vào file
                embeddings = {
                    "full_text": full_text_embedding.tolist(),
                    "combined_text": combined_text_embedding.tolist(),
                    "sections": {k: v.tolist() for k, v in section_embeddings.items()},
                }

                embedding_filename = f"cv_{application.id}.json"
                embedding_path = os.path.join(CV_DATA_DIR, embedding_filename)

                with open(embedding_path, "w", encoding="utf-8") as f:
                    json.dump(embeddings, f, ensure_ascii=False)

                # Cập nhật đường dẫn file
                cv_processed_data.embedding_file = embedding_filename
                cv_processed_data.save()

            return cv_processed_data

        except Exception as e:
            logger.error(f"Lỗi khi xử lý CV: {e}")
            logger.error(traceback.format_exc())
            return None


def process_cv_on_application(application):
    """
    Hàm được gọi khi có ứng viên nộp đơn
    """
    processor = CVProcessor()
    return processor.process_cv(application)
