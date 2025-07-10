from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Job
from users.choices import JobStatus
import logging
from AI.tasks import process_job_task

# Import module xử lý job data
try:
    from AI.job_processing import process_job_on_update, process_job_on_publish
except ImportError:
    # Nếu module chưa được tạo, tạo các hàm giả
    def process_job_on_publish(job):
        logging.warning(
            "AI.job_processing module not found. Job data processing skipped."
        )
        return None

    def process_job_on_update(job):
        logging.warning(
            "AI.job_processing module not found. Job data processing skipped."
        )
        return None


@receiver(post_save, sender=Job)
def job_post_save(sender, instance, created, **kwargs):
    """
    Signal để xử lý job sau khi lưu
    """
    # Nếu job mới được tạo, không cần xử lý ở đây vì đã được xử lý trong serializer
    if created:
        return

    # Nếu job được cập nhật và có trạng thái PUBLISHED, xử lý lại dữ liệu bất đồng bộ
    if instance.status == JobStatus.PUBLISHED:
        try:
            # Tìm và xóa dữ liệu cũ nếu có
            from AI.models import JobProcessedData

            JobProcessedData.objects.filter(job=instance).delete()

            # Gửi task xử lý job bất đồng bộ
            process_job_task.delay(str(instance.id), "update")
            logging.info(f"Job {instance.id} processing task queued")
        except Exception as e:
            logging.error(f"Error queueing job processing: {e}")
