import os
from django.conf import settings
import json


def extract_cv_content(cv_file):
    """
    Trích xuất nội dung từ file CV

    Phương pháp:
    1. Xác định loại file (pdf hoặc docx)
    2. Sử dụng thư viện phù hợp để trích xuất nội dung
    3. Trả về nội dung dưới dạng JSON

    Tham số:
    - cv_file: FileField object chứa CV

    Trả về:
    - Dictionary chứa nội dung đã trích xuất
    """
    file_path = cv_file.path
    file_name = os.path.basename(file_path).lower()

    # Cấu trúc kết quả
    result = {
        "raw_text": "",
        "sections": {},
        "extracted_skills": [],
        "extracted_education": [],
        "extracted_experience": [],
    }

    if file_name.endswith(".pdf"):
        # TODO: Sử dụng pdfplumber hoặc PyPDF2 để đọc nội dung PDF
        # Ví dụ:
        # import pdfplumber
        # with pdfplumber.open(file_path) as pdf:
        #     for page in pdf.pages:
        #         result['raw_text'] += page.extract_text() or ''
        pass

    elif file_name.endswith(".docx"):
        # TODO: Sử dụng python-docx để đọc nội dung DOCX
        # Ví dụ:
        # import docx
        # doc = docx.Document(file_path)
        # for para in doc.paragraphs:
        #     result['raw_text'] += para.text + '\n'
        pass

    # TODO: Phân tích nội dung thành các phần (sections)
    # TODO: Trích xuất kỹ năng, học vấn, kinh nghiệm

    return result


def analyze_cv_job_match(cv_content, job):
    """
    Phân tích mức độ phù hợp giữa CV và công việc

    Phương pháp:
    1. So sánh kỹ năng trong CV với yêu cầu công việc
    2. So sánh kinh nghiệm với yêu cầu công việc
    3. Tính điểm phù hợp tổng thể

    Tham số:
    - cv_content: Dictionary chứa nội dung CV đã trích xuất
    - job: Job object chứa thông tin công việc

    Trả về:
    - Điểm phù hợp (0-100)
    """
    # TODO: Phân tích yêu cầu công việc
    # TODO: So sánh CV với yêu cầu
    # TODO: Tính điểm phù hợp

    # Trả về điểm phù hợp giả định (sẽ được thay thế bằng logic thực tế)
    return 75.0
