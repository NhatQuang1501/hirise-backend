from django.apps import AppConfig
import os
import logging

logger = logging.getLogger(__name__)


class AIConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "AI"

    def ready(self):
        # Đảm bảo thư mục tồn tại khi ứng dụng khởi động
        from django.conf import settings

        job_data_dir = os.path.join(settings.BASE_DIR, "AI", "job_processed_data")
        cv_data_dir = os.path.join(settings.BASE_DIR, "AI", "cv_processed_data")

        try:
            os.makedirs(job_data_dir, exist_ok=True)
            os.makedirs(cv_data_dir, exist_ok=True)
            # Cấp quyền
            os.chmod(job_data_dir, 0o777)
            os.chmod(cv_data_dir, 0o777)
            logger.info(f"AI directories created and permissions set")
        except Exception as e:
            logger.error(f"Error setting up AI directories: {e}")
