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

# Setup logging
logger = logging.getLogger(__name__)

# Directory for processed CV data
CV_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "cv_processed_data")
os.makedirs(CV_DATA_DIR, exist_ok=True)

# Load spaCy language model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("Installing en_core_web_sm model...")
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")


class CVProcessor:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        # Initialize SBERT model
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            logger.error(f"Error initializing SBERT model: {e}")
            self.model = None

        # Load IT skills list
        try:
            with open(os.path.join(settings.BASE_DIR, "AI", "it_skills.txt"), "r") as f:
                self.it_skills = [line.strip().lower() for line in f.readlines()]
        except Exception as e:
            logger.error(f"Error loading IT skills list: {e}")
            self.it_skills = []

        # Define section patterns
        self.section_patterns = {
            "summary": [
                "summary",
                "professional summary",
                "profile",
                "about me",
                "personal statement",
                "objective",
                "career objective",
            ],
            "experience": [
                "experience",
                "work experience",
                "employment history",
                "work history",
                "professional experience",
                "experiences",
                "work experiences",
                "work history",
                "experience summary",
                "career history",
            ],
            "education": [
                "education",
                "academic background",
                "academic history",
                "qualifications",
                "educations",
                "education summary",
                "education history",
                "education background",
                "education summary",
                "education history",
                "education background",
            ],
            "skills": [
                "skills",
                "technical skills",
                "core competencies",
                "key skills",
                "expertise",
                "skills summary",
                "tech stack",
                "technical expertise",
            ],
            "projects": [
                "projects",
                "personal projects",
                "professional projects",
                "key projects",
                "projects summary",
                "project summary",
                "project experience",
                "highlighted projects",
            ],
            "certifications": [
                "certifications",
                "certificates",
                "professional certifications",
            ],
            "languages": [
                "language",
                "languages",
                "language proficiency",
                "language skills",
            ],
            "achievements": [
                "achievements",
                "awards",
                "honors",
                "accomplishments",
                "prizes",
                "awards",
                "prizes and awards",
            ],
        }

        # Section mapping for normalization
        self.section_mapping = {
            "summary": "summary",
            "profile": "summary",
            "about": "summary",
            "experience": "experience",
            "work": "experience",
            "employment": "experience",
            "education": "education",
            "academic": "education",
            "qualifications": "education",
            "skills": "skills",
            "technical": "skills",
            "competencies": "skills",
            "expertise": "skills",
            "projects": "projects",
            "certifications": "certifications",
            "certificates": "certifications",
            "languages": "languages",
            "achievements": "achievements",
            "awards": "achievements",
            "honors": "achievements",
        }

    def extract_text_from_pdf(self, pdf_path):
        try:
            text = ""
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    text += page.get_text()
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""

    def extract_text_from_docx(self, docx_path):
        try:
            text = docx2txt.process(docx_path)
            return text
        except Exception as e:
            logger.error(f"Error extracting text from DOCX: {e}")
            return ""

    def clean_text(self, text):
        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r"<.*?>", " ", text)

        # Normalize line breaks
        text = re.sub(r"\s*\n\s*", " ", text)

        # Normalize punctuation
        text = re.sub(r"\.(?=[A-Za-z])", ". ", text)

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def advanced_preprocessing(self, text):
        if not text:
            return ""

        # Basic cleaning
        text = self.clean_text(text)

        # Process IT abbreviations
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

        # Normalize technology names
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

    def enhance_cv_section(self, text, section_name):
        if not text:
            return ""

        # Apply advanced preprocessing
        text = self.advanced_preprocessing(text)

        # Extract sentences for better semantic understanding
        doc = nlp(text)
        sentences = [sent.text for sent in doc.sents]

        # Format based on section type
        if section_name == "skills":
            # Extract skill phrases
            skill_phrases = re.split(r"[,;•\n]|\s{2,}", text)
            skill_phrases = [
                phrase.strip() for phrase in skill_phrases if phrase.strip()
            ]

            # Format as a list
            formatted_text = "\n".join([f"• {skill}" for skill in skill_phrases])

        elif section_name in ["experience", "education"]:
            # Keep paragraph structure but enhance readability
            paragraphs = re.split(r"\n{2,}", text)
            formatted_text = "\n\n".join(paragraphs)

        else:
            # Default formatting for other sections
            formatted_text = "\n".join(sentences)

        return formatted_text

    def extract_cv_content(self, file_path):
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == ".pdf":
            return self.extract_text_from_pdf(file_path)
        elif file_ext == ".docx":
            return self.extract_text_from_docx(file_path)
        else:
            logger.error(f"Unsupported file format: {file_ext}")
            return ""

    def identify_sections_by_headings(self, text):
        if not text:
            return {}

        # Split text into lines
        lines = text.split("\n")

        # Identify potential section headings
        sections = {}
        current_section = "other"
        section_content = []

        for i, line in enumerate(lines):
            line_text = line.strip().lower()

            # Check if this line is a section heading
            is_heading = False
            section_type = None

            # Check against section patterns
            for section, patterns in self.section_patterns.items():
                for pattern in patterns:
                    # Match exact or with trailing colon or similar endings
                    if re.match(
                        rf"^{re.escape(pattern)}(\s*:|)$", line_text
                    ) or re.match(rf"^{re.escape(pattern)}s(\s*:|)$", line_text):
                        is_heading = True
                        section_type = section
                        break
                if is_heading:
                    break

            # If heading found, save previous section and start new one
            if is_heading and section_type:
                if section_content:
                    sections[current_section] = "\n".join(section_content)
                current_section = section_type
                section_content = []
            else:
                section_content.append(line)

        # Save the last section
        if section_content:
            sections[current_section] = "\n".join(section_content)

        return sections

    def get_standard_section_name(self, section_title):
        section_title = section_title.lower().strip()

        # Direct match with section patterns
        for section, patterns in self.section_patterns.items():
            if section_title in patterns:
                return section

        # Check for partial matches
        for key_word, section in self.section_mapping.items():
            if key_word in section_title:
                return section

        return "other"

    def find_most_similar_section(self, title):
        title_lower = title.lower()

        # Check direct matches first
        for section, patterns in self.section_patterns.items():
            for pattern in patterns:
                if pattern in title_lower or title_lower in pattern:
                    return section

        # Check for partial matches
        best_match = None
        highest_similarity = 0

        for section, patterns in self.section_patterns.items():
            for pattern in patterns:
                # Calculate simple word overlap similarity
                pattern_words = set(pattern.split())
                title_words = set(title_lower.split())

                if pattern_words and title_words:
                    common_words = pattern_words.intersection(title_words)
                    similarity = len(common_words) / max(
                        len(pattern_words), len(title_words)
                    )

                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = section

        # Return best match if similarity is above threshold
        if highest_similarity > 0.3:
            return best_match

        return "other"

    def extract_skills_from_text(self, text):
        if not text:
            return []

        # Apply advanced preprocessing
        text = self.advanced_preprocessing(text.lower())

        extracted_skills = []

        # Extract skills from IT skills list
        for skill in self.it_skills:
            if re.search(r"\b" + re.escape(skill) + r"\b", text):
                extracted_skills.append(skill)

        # Extract skills with experience levels
        skill_levels = {}

        # Pattern for years of experience
        experience_patterns = [
            r"(\d+)(?:\+)?\s*(?:years?|yrs?)\s*(?:of)?\s*experience\s*(?:with|in|using)?\s*([a-zA-Z0-9#\+\.\s]+)",
            r"([a-zA-Z0-9#\+\.\s]+)\s*(?:with)?\s*(\d+)(?:\+)?\s*(?:years?|yrs?)\s*(?:of)?\s*experience",
        ]

        for pattern in experience_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                if len(match.groups()) >= 2:
                    # Check if first group is years or skill based on pattern
                    if match.group(1).isdigit():
                        years = int(match.group(1))
                        skill_text = match.group(2).strip().lower()
                    else:
                        skill_text = match.group(1).strip().lower()
                        years = int(match.group(2))

                    # Clean up skill text
                    skill_text = re.sub(r"\s+", " ", skill_text)

                    # Check if this contains any known skills
                    for skill in self.it_skills:
                        if skill in skill_text:
                            skill_levels[skill] = years
                            if skill not in extracted_skills:
                                extracted_skills.append(skill)

        # Add experience level to skills
        final_skills = []
        for skill in extracted_skills:
            if skill in skill_levels:
                final_skills.append(f"{skill} ({skill_levels[skill]} years)")
            else:
                final_skills.append(skill)

        return final_skills

    def process_cv(self, application):
        try:
            if not application.cv or not application.cv.file:
                logger.error("No CV file found in application")
                return None

            # Create a temporary file to process
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file_path = temp_file.name

                # Write CV content to temporary file
                for chunk in application.cv.file.chunks():
                    temp_file.write(chunk)

            try:
                # Extract text from CV
                cv_text = self.extract_cv_content(temp_file_path)
                if not cv_text:
                    logger.error("Failed to extract text from CV")
                    return None

                # Clean and preprocess text
                cv_text = self.clean_text(cv_text)

                # Identify sections
                sections = self.identify_sections_by_headings(cv_text)

                # Process sections
                processed_sections = {}
                for section_name, content in sections.items():
                    if section_name != "other":
                        processed_sections[section_name] = self.enhance_cv_section(
                            content, section_name
                        )

                # Extract key information
                summary = processed_sections.get("summary", "")
                experience = processed_sections.get("experience", "")
                education = processed_sections.get("education", "")
                skills = processed_sections.get("skills", "")
                projects = processed_sections.get("projects", "")
                certifications = processed_sections.get("certifications", "")
                achievements = processed_sections.get("achievements", "")

                # Extract skills
                extracted_skills = self.extract_skills_from_text(
                    skills + " " + experience
                )

                # Extract experience details with years
                experience_details = {}
                skill_patterns = [
                    re.escape(skill.split(" (")[0]) for skill in extracted_skills
                ]

                for skill in extracted_skills:
                    base_skill = skill.split(" (")[0]
                    if " (" in skill and "year" in skill.lower():
                        years_match = re.search(r"\((\d+)", skill)
                        if years_match:
                            experience_details[base_skill] = int(years_match.group(1))

                # Create combined text for embedding
                combined_text = f"{summary} {experience} {education} {skills}"

                # Generate embeddings
                full_text_embedding = self.model.encode(cv_text)
                combined_text_embedding = self.model.encode(combined_text)

                # Generate section embeddings
                section_embeddings = {}
                for section_name, content in processed_sections.items():
                    if content.strip():
                        section_embeddings[section_name] = self.model.encode(content)

                # Save embeddings to file
                embeddings = {
                    "full_text": full_text_embedding.tolist(),
                    "combined_text": combined_text_embedding.tolist(),
                    "sections": {k: v.tolist() for k, v in section_embeddings.items()},
                }

                embedding_filename = f"cv_{application.cv.id}.json"
                embedding_path = os.path.join(CV_DATA_DIR, embedding_filename)

                with open(embedding_path, "w") as f:
                    json.dump(embeddings, f)

                # Save processed data to database
                cv_data, created = CVProcessedData.objects.update_or_create(
                    cv=application.cv,
                    defaults={
                        "summary": summary,
                        "experience": experience,
                        "education": education,
                        "skills": skills,
                        "projects": projects,
                        "certifications": certifications,
                        "extracted_skills": extracted_skills,
                        "experience_details": experience_details,
                        "achievements": achievements,
                    },
                )

                return cv_data
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Error processing CV: {e}")
            logger.error(traceback.format_exc())
            return None


def process_cv_on_application(application):
    processor = CVProcessor()
    return processor.process_cv(application)
