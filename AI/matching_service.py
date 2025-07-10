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
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            logger.error(f"Error initializing SBERT model: {e}")
            self.model = None

        self.JOB_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "job_processed_data")
        self.CV_DATA_DIR = os.path.join(settings.BASE_DIR, "AI", "cv_processed_data")

        try:
            with open(os.path.join(settings.BASE_DIR, "AI", "it_skills.txt"), "r") as f:
                self.it_skills = [line.strip().lower() for line in f.readlines()]
        except Exception as e:
            logger.error(f"Error loading IT skills list: {e}")
            self.it_skills = []

        # Weights for matching components
        self.exact_match_weight = 0.3
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
        # Default weights
        weights = {
            "job_requirements_cv_skills": 0.25,
            "job_responsibilities_cv_experience": 0.20,
            "job_skills_cv_skills": 0.15,
            "job_title_cv_summary": 0.10,
            "job_preferred_cv_skills": 0.10,
            "combined_text": 0.05,
            "context_match": 0.15,
        }

        # Adjust based on job requirements detail
        if (
            job_data.basic_requirements
            and len(job_data.basic_requirements.split()) > 100
        ):
            weights["job_requirements_cv_skills"] += 0.05
            weights["combined_text"] -= 0.05

        # Adjust based on CV skills count
        if (
            hasattr(cv_data, "extracted_skills")
            and cv_data.extracted_skills
            and len(cv_data.extracted_skills) > 10
        ):
            weights["job_skills_cv_skills"] += 0.05
            weights["job_title_cv_summary"] -= 0.05

        # Adjust based on CV experience detail
        if cv_data.experience and len(cv_data.experience.split()) > 200:
            weights["job_responsibilities_cv_experience"] += 0.05
            weights["job_preferred_cv_skills"] -= 0.05

        # Adjust based on specific experience requirements
        if (
            hasattr(job_data, "experience_requirements")
            and job_data.experience_requirements
        ):
            weights["context_match"] += 0.05
            weights["combined_text"] -= 0.05

        # Normalize weights
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}

    def match_with_context(self, job_data, cv_data):
        # Context-aware matching
        context_scores = {}

        # Match experience requirements with candidate experience
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
                    # Calculate score based on experience ratio
                    ratio = min(candidate_years / required_years, 1.5)  # Cap at 150%
                    context_scores[f"experience_{tech}"] = ratio
                else:
                    context_scores[f"experience_{tech}"] = 0

        # Match skills with priority levels
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
                # Look for similar skills
                for cv_skill in extracted_skills:
                    if skill_lower in cv_skill or cv_skill in skill_lower:
                        context_scores[f"skill_{skill_lower}"] = 0.7
                        break
                else:
                    context_scores[f"skill_{skill_lower}"] = 0

        # Calculate weighted average score
        if context_scores:
            weighted_score = 0
            total_weight = 0

            for item, score in context_scores.items():
                if item.startswith("experience_"):
                    weight = 2.0  # Higher weight for experience
                else:
                    weight = 1.0  # Standard weight for skills

                weighted_score += score * weight
                total_weight += weight

            return weighted_score / total_weight if total_weight > 0 else 0
        else:
            return 0

    def generate_match_explanation(self, job_data, cv_data, match_scores):
        # Identify strengths (matching skills)
        strengths = []

        # Get skills from job and CV
        job_skills = job_data.skills if job_data.skills else []
        cv_skills = []
        if hasattr(cv_data, "extracted_skills") and cv_data.extracted_skills:
            cv_skills = [
                skill.split(" (")[0].lower() if " (" in skill else skill.lower()
                for skill in cv_data.extracted_skills
            ]

        # Find matching skills
        for skill in job_skills:
            skill_lower = skill.lower()
            if any(
                skill_lower in cv_skill or cv_skill in skill_lower
                for cv_skill in cv_skills
            ):
                strengths.append(f"Candidate has experience with {skill}")

        # Check experience
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

        # Identify weaknesses (missing skills)
        weaknesses = []

        # Find missing skills
        for skill in job_skills:
            skill_lower = skill.lower()
            if not any(
                skill_lower in cv_skill or cv_skill in skill_lower
                for cv_skill in cv_skills
            ):
                weaknesses.append(f"Job requires {skill} which was not found in the CV")

        # Check missing experience
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

        # Generate overall explanation
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
        try:
            if file_path.endswith(".npy"):
                return np.load(file_path)
            elif file_path.endswith(".json"):
                with open(file_path, "r") as f:
                    data = json.load(f)
                return np.array(data["combined_text"])
            else:
                logger.error(f"Unsupported embedding file format: {file_path}")
                return None
        except Exception as e:
            logger.error(f"Error loading embedding from {file_path}: {e}")
            return None

    def compute_embedding(self, text):
        if not text or not self.model:
            return None

        try:
            return self.model.encode(text)
        except Exception as e:
            logger.error(f"Error computing embedding: {e}")
            return None

    def compute_similarity(self, text1, text2):
        if not text1 or not text2 or not self.model:
            return 0.0

        try:
            embedding1 = self.model.encode(text1)
            embedding2 = self.model.encode(text2)
            return util.cos_sim(embedding1, embedding2).item()
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0

    def compute_similarity_from_embeddings(self, embedding1, embedding2):
        if embedding1 is None or embedding2 is None:
            return 0.0

        try:
            return util.cos_sim(embedding1, embedding2).item()
        except Exception as e:
            logger.error(f"Error computing similarity from embeddings: {e}")
            return 0.0

    def compute_exact_match_score(self, job_skills, cv_skills):
        if not job_skills or not cv_skills:
            return 0.0

        # Convert to lowercase for case-insensitive matching
        job_skills_lower = [skill.lower() for skill in job_skills]
        cv_skills_lower = [skill.lower() for skill in cv_skills]

        # Count matches
        matches = sum(1 for skill in job_skills_lower if skill in cv_skills_lower)

        # Calculate score as percentage of matched skills
        return matches / len(job_skills) if job_skills else 0.0

    def compute_detailed_matching_scores(self, job_data, cv_data):
        semantic_scores = {}

        # Load CV embeddings
        cv_file_path = os.path.join(self.CV_DATA_DIR, f"cv_{cv_data.id}.json")
        if not os.path.exists(cv_file_path):
            logger.error(f"CV embedding file not found: {cv_file_path}")
            return {}

        with open(cv_file_path, "r") as f:
            cv_embeddings = json.load(f)

        # Load job embedding
        job_file_path = os.path.join(self.JOB_DATA_DIR, f"job_{job_data.job.id}.npy")
        if not os.path.exists(job_file_path):
            logger.error(f"Job embedding file not found: {job_file_path}")
            return {}

        job_embedding = np.load(job_file_path)

        # Compare job requirements with CV skills
        if job_data.basic_requirements and cv_embeddings["sections"].get("skills"):
            job_req_embedding = self.compute_embedding(job_data.basic_requirements)
            cv_skills_embedding = np.array(cv_embeddings["sections"]["skills"])
            semantic_scores["job_requirements_cv_skills"] = (
                self.compute_similarity_from_embeddings(
                    job_req_embedding, cv_skills_embedding
                )
            )

        # Compare job requirements with CV experience
        if job_data.basic_requirements and cv_embeddings["sections"].get("experience"):
            job_req_embedding = self.compute_embedding(job_data.basic_requirements)
            cv_exp_embedding = np.array(cv_embeddings["sections"]["experience"])
            semantic_scores["job_requirements_cv_experience"] = (
                self.compute_similarity_from_embeddings(
                    job_req_embedding, cv_exp_embedding
                )
            )

        # Compare job skills with CV skills
        if job_data.skills and cv_data.extracted_skills:
            job_skills_text = ", ".join(job_data.skills)
            cv_skills_text = ", ".join(cv_data.extracted_skills)
            job_skills_embedding = self.compute_embedding(job_skills_text)
            cv_skills_embedding = self.compute_embedding(cv_skills_text)
            semantic_scores["job_skills_cv_skills"] = (
                self.compute_similarity_from_embeddings(
                    job_skills_embedding, cv_skills_embedding
                )
            )

            # Also compute exact match score
            exact_match = self.compute_exact_match_score(
                job_data.skills, cv_data.extracted_skills
            )
            semantic_scores["exact_skills_match"] = exact_match

        # Compare job responsibilities with CV experience
        if job_data.responsibilities and cv_embeddings["sections"].get("experience"):
            job_resp_embedding = self.compute_embedding(job_data.responsibilities)
            cv_exp_embedding = np.array(cv_embeddings["sections"]["experience"])
            semantic_scores["job_responsibilities_cv_experience"] = (
                self.compute_similarity_from_embeddings(
                    job_resp_embedding, cv_exp_embedding
                )
            )

        # Compare job title with CV summary
        if job_data.job.title and cv_embeddings["sections"].get("summary"):
            job_title_embedding = self.compute_embedding(job_data.job.title)
            cv_summary_embedding = np.array(cv_embeddings["sections"]["summary"])
            semantic_scores["job_title_cv_summary"] = (
                self.compute_similarity_from_embeddings(
                    job_title_embedding, cv_summary_embedding
                )
            )

        # Compare preferred skills with CV skills
        if job_data.job.preferred_skills and cv_embeddings["sections"].get("skills"):
            preferred_skills_text = ", ".join(job_data.job.preferred_skills)
            preferred_skills_embedding = self.compute_embedding(preferred_skills_text)
            cv_skills_embedding = np.array(cv_embeddings["sections"]["skills"])
            semantic_scores["job_preferred_cv_skills"] = (
                self.compute_similarity_from_embeddings(
                    preferred_skills_embedding, cv_skills_embedding
                )
            )

        # Compare full texts
        semantic_scores["combined_text"] = self.compute_similarity_from_embeddings(
            job_embedding, np.array(cv_embeddings["combined_text"])
        )

        # Add context-aware matching score
        context_score = self.match_with_context(job_data, cv_data)
        semantic_scores["context_match"] = context_score

        return semantic_scores

    def compute_weighted_score(self, detailed_scores):
        if not detailed_scores:
            return 0.0

        # Get dynamic weights based on available scores
        weights = {
            k: self.section_weights.get(k, 0.1)
            for k in detailed_scores.keys()
            if k != "exact_skills_match"
        }

        # Normalize weights to sum to (1 - exact_match_weight)
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {
                k: v / total_weight * (1 - self.exact_match_weight)
                for k, v in weights.items()
            }

        # Calculate weighted score
        weighted_score = sum(detailed_scores[k] * weights[k] for k in weights.keys())

        # Add exact match component if available
        if "exact_skills_match" in detailed_scores:
            weighted_score += (
                detailed_scores["exact_skills_match"] * self.exact_match_weight
            )

        return weighted_score

    def match_job_cv(self, job_id, application_id=None, cv_id=None):
        try:
            # Get job data
            job_data = JobProcessedData.objects.filter(job_id=job_id).first()
            if not job_data:
                logger.error(f"No processed data found for job {job_id}")
                return None

            # Get CV data based on application_id or cv_id
            cv_data = None
            if application_id:
                application = JobApplication.objects.filter(id=application_id).first()
                if application and application.cv:
                    cv_data = CVProcessedData.objects.filter(cv=application.cv).first()
            elif cv_id:
                cv_data = CVProcessedData.objects.filter(cv_id=cv_id).first()

            if not cv_data:
                logger.error(
                    f"No processed CV data found for application {application_id} or CV {cv_id}"
                )
                return None

            # Compute detailed matching scores
            detailed_scores = self.compute_detailed_matching_scores(job_data, cv_data)
            if not detailed_scores:
                logger.error("Failed to compute detailed matching scores")
                return None

            # Compute overall match score
            match_score = self.compute_weighted_score(detailed_scores)

            # Generate match explanation
            match_explanation = self.generate_match_explanation(
                job_data, cv_data, detailed_scores
            )

            # Create or update match record
            job_cv_match, created = JobCVMatch.objects.update_or_create(
                job_id=job_id,
                cv_id=cv_data.cv.id if cv_data.cv else None,
                defaults={
                    "match_score": match_score,
                    "match_details": {
                        "overall_score": match_score,
                        "detail_scores": detailed_scores,
                        "explanation": match_explanation,
                    },
                },
            )

            return job_cv_match
        except Exception as e:
            logger.error(f"Error in match_job_cv: {e}")
            logger.error(traceback.format_exc())
            return None

    def match_job_with_all_applications(self, job_id):
        try:
            # Get job
            job = Job.objects.filter(id=job_id).first()
            if not job:
                logger.error(f"Job not found: {job_id}")
                return []

            # Get all applications for this job
            applications = JobApplication.objects.filter(job=job)

            results = []
            for application in applications:
                if application.cv:
                    match_result = self.match_job_cv(
                        job_id, application_id=application.id
                    )
                    if match_result:
                        results.append(match_result)

            return results
        except Exception as e:
            logger.error(f"Error in match_job_with_all_applications: {e}")
            logger.error(traceback.format_exc())
            return []
