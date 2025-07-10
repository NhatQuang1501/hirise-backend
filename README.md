# HiRise - Tech Job Platform Backend

Backend system for the HiRise tech recruitment platform, built with Django and Python, integrating AI technology to optimize the recruitment process.

## 🚀 Features

- Job posting and candidate profile management
- Automated CV processing and analysis
- Intelligent matching between CVs and job requirements
- AI-based compatibility assessment system
- RESTful API for frontend integration
- Authentication and user authorization

## 🛠️ Technologies

- **Framework:** Django
- **Database:** PostgreSQL
- **Asynchronous Processing:** Celery
- **Cache:** Redis
- **AI/ML:** SentenceTransformer, spaCy
- **File Processing:** PyMuPDF, docx2txt
- **Authentication:** JWT
- **File Storage:** Digital Ocean Spaces (S3-compatible)

## 📦 Installation

1. Clone repository:

```bash
git clone https://github.com/NhatQuang1501/hirise-backend.git
cd hirise-backend
```

2. Create and activate virtual environment:

```bash
python -m venv env
# Windows
env\Scripts\activate
# Linux/MacOS
source env/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install spaCy model:

```bash
python -m spacy download en_core_web_sm
```

5. Start the server:

```bash
python manage.py runserver
```

## 🔧 Project Structure

```
backend/
├── AI/                # AI processing module
│   ├── cv_processing.py     # CV processing
│   ├── job_processing.py    # Job posting processing
│   ├── matching_service.py  # Matching service
│   └── it_skills.txt        # IT skills list
├── application/       # Application management module
├── digital_ocean_space/ # File storage configuration
├── hirise/            # Main project configuration
├── jobs/              # Job posting management module
├── users/             # User management module
└── manage.py          # Django management script
```

## 📊 AI Module

HiRise uses AI technology to analyze CVs and job postings:

1. **CV Processor**: Extracts information from PDF/DOCX files, segments content, identifies skills
2. **JD Processor**: Analyzes job requirements, extracts necessary skills
3. **Matching Service**: Compares similarity between CVs and job requirements