import os
import re
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
from django.conf import settings
from .models import JobProcessedData
import traceback

# Setup logging
logger = logging.getLogger(__name__)

# Directory for processed job data
JOB_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "job_processed_data")
os.makedirs(JOB_DATA_DIR, exist_ok=True)


class JobProcessor:
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

    def enhance_semantic_structure(self, text, section_title):
        if not text:
            return ""

        # Apply advanced preprocessing
        text = self.advanced_preprocessing(text)

        # Split items in list
        items = re.split(r"(?:\r?\n)|(?:•|\*|\-|\d+\.)\s*", text)
        items = [item.strip() for item in items if item.strip()]

        # Format with clear structure
        formatted_text = f"{section_title}:\n"
        for i, item in enumerate(items, 1):
            formatted_text += f"• {item}\n"

        return formatted_text

    def extract_skills_from_text(self, text, skill_tags=None):
        if not text:
            return []

        # Apply advanced preprocessing
        text = self.advanced_preprocessing(text.lower())

        extracted_skills = []

        # Search from skill_tags (from database)
        if skill_tags:
            for skill in skill_tags:
                if re.search(r"\b" + re.escape(skill.name.lower()) + r"\b", text):
                    extracted_skills.append(skill.name)

        # Search from IT skills list
        for skill in self.it_skills:
            if skill not in [s.lower() for s in extracted_skills] and re.search(
                r"\b" + re.escape(skill) + r"\b", text
            ):
                extracted_skills.append(skill)

        # Extract skills with required levels
        skill_levels = self.extract_skill_levels(text)

        # Combine results
        final_skills = []
        for skill in extracted_skills:
            if skill.lower() in skill_levels:
                final_skills.append(f"{skill} ({skill_levels[skill.lower()]})")
            else:
                final_skills.append(skill)

        return final_skills

    def extract_skill_levels(self, text):
        if not text:
            return {}

        skill_levels = {}

        # Look for skill level patterns
        level_patterns = [
            (
                r"(advanced|expert|proficient)\s+(?:knowledge\s+(?:of|in)\s+)?([a-zA-Z0-9\+\#\.]+)",
                "expert",
            ),
            (
                r"([a-zA-Z0-9\+\#\.]+)\s+(?:at\s+)?(advanced|expert|proficient)(?:\s+level)?",
                "expert",
            ),
            (
                r"(intermediate)\s+(?:knowledge\s+(?:of|in)\s+)?([a-zA-Z0-9\+\#\.]+)",
                "intermediate",
            ),
            (
                r"([a-zA-Z0-9\+\#\.]+)\s+(?:at\s+)?(intermediate)(?:\s+level)?",
                "intermediate",
            ),
            (
                r"(basic|beginner)\s+(?:knowledge\s+(?:of|in)\s+)?([a-zA-Z0-9\+\#\.]+)",
                "beginner",
            ),
            (
                r"([a-zA-Z0-9\+\#\.]+)\s+(?:at\s+)?(basic|beginner)(?:\s+level)?",
                "beginner",
            ),
        ]

        for pattern, level in level_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) >= 2:
                    # Check which group is the skill based on pattern
                    if match.group(1).lower() in [
                        "advanced",
                        "expert",
                        "proficient",
                        "intermediate",
                        "basic",
                        "beginner",
                    ]:
                        skill = match.group(2).lower()
                    else:
                        skill = match.group(1).lower()

                    # Clean up skill name
                    skill = skill.strip()

                    # Check if this is a known skill
                    for known_skill in self.it_skills:
                        if (
                            skill == known_skill
                            or skill in known_skill
                            or known_skill in skill
                        ):
                            skill_levels[known_skill] = level
                            break
                    else:
                        # If not found in known skills but seems valid, add it
                        if len(skill) > 2 and not re.search(
                            r"\b(and|with|for|the|or)\b", skill
                        ):
                            skill_levels[skill] = level

        return skill_levels

    def extract_experience_requirements(self, text):
        if not text:
            return {}

        # Apply advanced preprocessing
        text = self.advanced_preprocessing(text.lower())

        experience_requirements = {}

        # Look for patterns like "X years of experience in Y"
        patterns = [
            r"(\d+)(?:\+)?\s*(?:years|yrs)(?:\s*of)?\s*experience\s*(?:with|in|using)?\s*([a-zA-Z0-9\+\#\.\s]+)",
            r"experience\s*(?:with|in|using)?\s*([a-zA-Z0-9\+\#\.\s]+)(?:\s*for)?\s*(?:at\s*least)?\s*(\d+)(?:\+)?\s*(?:years|yrs)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                if len(match.groups()) >= 2:
                    # Determine which group is years and which is skill
                    if match.group(1).isdigit():
                        years = int(match.group(1))
                        skill_text = match.group(2).strip()
                    else:
                        skill_text = match.group(1).strip()
                        years = int(match.group(2))

                    # Clean up skill text
                    skill_text = re.sub(r"\s+", " ", skill_text)

                    # Check if this contains any known skills
                    for skill in self.it_skills:
                        if skill in skill_text:
                            experience_requirements[skill] = years
                            break
                    else:
                        # If no specific skill found, use the whole phrase
                        # but clean it up to be more like a technology name
                        clean_skill = re.sub(
                            r"\b(and|with|for|the|or)\b", "", skill_text
                        )
                        clean_skill = re.sub(r"\s+", " ", clean_skill).strip()

                        if clean_skill and len(clean_skill) > 2:
                            experience_requirements[clean_skill] = years

        return experience_requirements

    def normalize_technology_name(self, tech_name):
        if not tech_name:
            return ""

        # Convert to lowercase and trim
        tech = tech_name.lower().strip()

        # Handle common variations
        tech_mapping = {
            "js": "javascript",
            "ts": "typescript",
            "py": "python",
            "c#": "csharp",
            ".net": "dotnet",
            "react.js": "react",
            "reactjs": "react",
            "node.js": "node",
            "nodejs": "node",
            "vue.js": "vue",
            "vuejs": "vue",
            "angular.js": "angular",
            "angularjs": "angular",
            "next.js": "nextjs",
            "mongodb": "mongodb",
            "postgres": "postgresql",
            "postgresql": "postgresql",
            "mysql": "mysql",
            "mssql": "mssql",
            "sql server": "mssql",
        }

        # Check for exact matches
        if tech in tech_mapping:
            return tech_mapping[tech]

        # Check for partial matches
        for key, value in tech_mapping.items():
            if key in tech:
                return value

        # Return original if no match
        return tech

    def process_job(self, job):
        try:
            # Extract job details
            title = job.title or ""
            description = job.description or ""
            responsibilities = job.responsibilities or ""
            basic_requirements = job.basic_requirements or ""
            preferred_skills = job.preferred_skills or []

            # Clean and preprocess text
            title_clean = self.clean_text(title)
            description_clean = self.clean_text(description)
            responsibilities_clean = self.clean_text(responsibilities)
            basic_requirements_clean = self.clean_text(basic_requirements)

            # Extract skills from requirements
            extracted_skills = self.extract_skills_from_text(
                basic_requirements_clean + " " + responsibilities_clean,
                job.skill_tags.all() if hasattr(job, "skill_tags") else None,
            )

            # Extract experience requirements
            experience_requirements = self.extract_experience_requirements(
                basic_requirements_clean
            )

            # Create combined text for embedding
            combined_text = f"{title_clean} {description_clean} {responsibilities_clean} {basic_requirements_clean}"
            if preferred_skills:
                preferred_skills_text = ", ".join(preferred_skills)
                combined_text += f" {preferred_skills_text}"

            # Create embedding
            embedding = self.model.encode(combined_text)

            # Save embedding to file
            embedding_filename = f"job_{job.id}.npy"
            embedding_path = os.path.join(JOB_DATA_DIR, embedding_filename)
            np.save(embedding_path, embedding)

            # Save processed data to database
            job_data, created = JobProcessedData.objects.update_or_create(
                job=job,
                defaults={
                    "title": title_clean,
                    "description": description_clean,
                    "responsibilities": responsibilities_clean,
                    "basic_requirements": basic_requirements_clean,
                    "skills": extracted_skills,
                    "experience_requirements": experience_requirements,
                    "embedding_file": embedding_filename,
                },
            )

            return job_data

        except Exception as e:
            logger.error(f"Error processing job: {e}")
            logger.error(traceback.format_exc())
            return None


def process_job_on_publish(job):
    processor = JobProcessor()
    return processor.process_job(job)


def process_job_on_update(job):
    processor = JobProcessor()
    return processor.process_job(job)
