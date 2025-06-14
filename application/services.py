import os
from django.conf import settings
import logging

# Imports từ AI module
try:
    from AI.cv_processing import process_cv_on_application
    from AI.matching_service import MatchingService
except ImportError:
    # Nếu module chưa được tạo, tạo hàm giả
    def process_cv_on_application(application):
        logging.warning("AI.cv_processing module not found. CV processing skipped.")
        return None

    class MatchingService:
        def match_job_cv(self, job_id, application_id=None, cv_id=None):
            logging.warning("AI.matching_service module not found. Matching skipped.")
            return None


logger = logging.getLogger(__name__)


def process_job_application(application):
    """
    Xử lý đơn ứng tuyển mới
    1. Xử lý CV để trích xuất thông tin
    2. Đánh giá sự phù hợp với công việc
    """
    try:
        # Xử lý CV để trích xuất thông tin
        cv_data = process_cv_on_application(application)

        # Nếu xử lý CV thành công, đánh giá sự phù hợp với công việc
        if cv_data:
            try:
                # Đánh giá sự phù hợp với công việc
                matching_service = MatchingService()
                match_result = matching_service.match_job_cv(
                    job_id=application.job.id, application_id=application.id
                )

                if match_result:
                    logger.info(
                        f"Evaluated match for application {application.id}: {match_result.match_score:.2f}%"
                    )
                else:
                    logger.warning(
                        f"Cannot evaluate match for application {application.id}"
                    )
            except Exception as e:
                logger.error(f"Error evaluating match: {e}")
        else:
            logger.warning(f"Cannot process CV for application {application.id}")
    except Exception as e:
        logger.error(f"Error processing application {application.id}: {e}")

    return application


def evaluate_applications_for_job(job_id):
    """
    Đánh giá lại tất cả đơn ứng tuyển cho một công việc
    """
    try:
        matching_service = MatchingService()
        results = matching_service.match_job_with_all_applications(job_id)

        if results:
            logger.info(f"Evaluated {len(results)} applications for job {job_id}")
            return results
        else:
            logger.warning(f"No applications found for job {job_id}")
            return []
    except Exception as e:
        logger.error(f"Error evaluating applications for job {job_id}: {e}")
        return []
