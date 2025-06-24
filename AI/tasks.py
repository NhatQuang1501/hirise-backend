from celery import shared_task
from .cv_processing import process_cv_on_application
from .job_processing import process_job_on_publish, process_job_on_update
from application.models import JobApplication
from jobs.models import Job
import logging


@shared_task
def process_cv_task(application_id):
    try:
        application = JobApplication.objects.get(id=application_id)
        return process_cv_on_application(application)
    except Exception as e:
        logging.error(f"Error processing CV: {e}")
        return None


@shared_task
def process_job_task(job_id, action="update"):
    try:
        job = Job.objects.get(id=job_id)
        if action == "publish":
            return process_job_on_publish(job)
        else:
            return process_job_on_update(job)
    except Exception as e:
        logging.error(f"Error processing job: {e}")
        return None
