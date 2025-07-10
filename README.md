# HiRise - Tech Job Platform Backend

Hệ thống backend cho nền tảng tuyển dụng công nghệ HiRise, được xây dựng với Django và Python, tích hợp công nghệ AI để tối ưu hóa quá trình tuyển dụng.

## 🚀 Tính năng

- Quản lý tin tuyển dụng và hồ sơ ứng viên
- Xử lý và phân tích CV tự động
- Đối sánh thông minh giữa CV và yêu cầu công việc
- Hệ thống đánh giá độ phù hợp dựa trên AI
- API RESTful cho frontend
- Xác thực và phân quyền người dùng

## 🛠️ Công nghệ sử dụng

- **Framework:** Django
- **Cơ sở dữ liệu:** PostgreSQL
- **Xử lý bất đồng bộ:** Celery
- **Cache:** Redis
- **AI/ML:** SentenceTransformer, spaCy
- **Xử lý file:** PyMuPDF, docx2txt
- **Xác thực:** JWT
- **Lưu trữ file:** Digital Ocean Spaces (S3-compatible)

## 📦 Cài đặt

1. Clone repository:

```bash
git clone https://github.com/NhatQuang1501/hirise-backend.git
cd hirise-backend
```

2. Tạo và kích hoạt môi trường ảo:

```bash
python -m venv env
# Windows
env\Scripts\activate
# Linux/MacOS
source env/bin/activate
```

3. Cài đặt các gói phụ thuộc:

```bash
pip install -r requirements.txt
```

4. Cài đặt mô hình spaCy:

```bash
python -m spacy download en_core_web_sm
```

5. Khởi động server:

```bash
python manage.py runserver
```

## 🔧 Cấu trúc dự án

```
backend/
├── AI/                # Module xử lý AI
│   ├── cv_processing.py     # Xử lý CV
│   ├── job_processing.py    # Xử lý tin tuyển dụng
│   ├── matching_service.py  # Dịch vụ đối sánh
│   └── it_skills.txt        # Danh sách kỹ năng IT
├── application/       # Module quản lý ứng tuyển
├── digital_ocean_space/ # Cấu hình lưu trữ file
├── hirise/            # Cấu hình chính của dự án
├── jobs/              # Module quản lý tin tuyển dụng
├── users/             # Module quản lý người dùng
└── manage.py          # Script quản lý Django
```


## 📊 Module AI

HiRise sử dụng công nghệ AI để phân tích CV và tin tuyển dụng:

1. **CV Processor**: Trích xuất thông tin từ file PDF/DOCX, phân đoạn nội dung, nhận diện kỹ năng
2. **JD Processor**: Phân tích yêu cầu công việc, trích xuất kỹ năng cần thiết
3. **Matching Service**: So sánh độ tương đồng giữa CV và yêu cầu công việc
