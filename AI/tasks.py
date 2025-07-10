from celery import shared_task
from .cv_processing import process_cv_on_application
from .job_processing import process_job_on_publish, process_job_on_update
from .matching_service import MatchingService
from application.models import JobApplication
from jobs.models import Job
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_cv_task(application_id):
    """
    Task xử lý CV bất đồng bộ
    """
    try:
        application = JobApplication.objects.get(id=application_id)
        result = process_cv_on_application(application)
        logger.info(f"Successfully processed CV for application {application_id}")
        return result
    except Exception as e:
        logger.error(f"Error processing CV: {e}")
        return None


@shared_task
def process_job_task(job_id, action="update"):
    """
    Task xử lý job bất đồng bộ
    """
    try:
        job = Job.objects.get(id=job_id)
        if action == "publish":
            result = process_job_on_publish(job)
        else:
            result = process_job_on_update(job)
        logger.info(f"Successfully processed job {job_id}")
        return result
    except Exception as e:
        logger.error(f"Error processing job: {e}")
        return None
