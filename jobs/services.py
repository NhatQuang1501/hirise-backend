from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from jobs.models import Job, JobApplication
from users.choices import JobStatus, ApplicationStatus


class JobService:
    """
    Service class for handling complex business logic related to Job
    """

    @staticmethod
    @transaction.atomic
    def publish_job(job):
        """
        Publish a job and handle related logic
        """
        # Kiểm tra điều kiện đăng tải
        if job.status == JobStatus.PUBLISHED:
            raise ValueError("Job is already published")
        if job.status == JobStatus.CLOSED:
            raise ValueError("Cannot republish a closed job")

        # Kiểm tra các trường bắt buộc
        required_fields = ["title", "description", "job_type", "experience_level"]
        missing_fields = []

        for field in required_fields:
            if not getattr(job, field):
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # Cập nhật trạng thái
        job.status = JobStatus.PUBLISHED
        job.save(update_fields=["status", "updated_at"])

        # Gửi thông báo đến các ứng viên phù hợp (có thể implement sau)
        # NotificationService.notify_matching_applicants(job)

        return job

    @staticmethod
    @transaction.atomic
    def close_job(job, reason=None):
        """
        Close a job and reject all pending applications
        """
        if job.status == JobStatus.CLOSED:
            raise ValueError("Job is already closed")

        # Cập nhật trạng thái và ngày đóng
        job.status = JobStatus.CLOSED
        job.closed_date = timezone.now().date()
        job.save(update_fields=["status", "closed_date", "updated_at"])

        # Từ chối tất cả đơn ứng tuyển đang chờ xử lý
        pending_applications = JobApplication.objects.filter(
            job=job, status__in=[ApplicationStatus.PENDING, ApplicationStatus.REVIEWING]
        )

        rejection_note = "Job is closed"
        if reason:
            rejection_note += f": {reason}"

        pending_applications.update(
            status=ApplicationStatus.REJECTED, note=rejection_note
        )

        # Gửi email thông báo đến các ứng viên (có thể implement sau)
        # for application in pending_applications:
        #     JobApplicationService.send_rejection_email(application)

        return job

    @staticmethod
    def get_job_statistics(job):
        """
        Get statistics about a job
        """
        stats = {
            # Tổng số đơn ứng tuyển
            "total_applications": job.applications.count(),
            # Phân loại theo trạng thái
            "pending_applications": job.applications.filter(
                status=ApplicationStatus.PENDING
            ).count(),
            "reviewing_applications": job.applications.filter(
                status=ApplicationStatus.REVIEWING
            ).count(),
            "accepted_applications": job.applications.filter(
                status=ApplicationStatus.ACCEPTED
            ).count(),
            "rejected_applications": job.applications.filter(
                status=ApplicationStatus.REJECTED
            ).count(),
            # Thống kê views
            "total_views": job.views.count(),
            # Thời gian tồn tại
            "days_active": (timezone.now().date() - job.created_at.date()).days,
        }

        # Tính tỷ lệ chuyển đổi (conversion rate)
        if stats["total_views"] > 0:
            stats["application_rate"] = (
                stats["total_applications"] / stats["total_views"]
            ) * 100
        else:
            stats["application_rate"] = 0

        return stats


class JobApplicationService:
    """
    Service class for handling business logic related to JobApplication
    """

    @staticmethod
    @transaction.atomic
    def process_application_status_change(application, new_status, note=None):
        """
        Process status changes for job applications
        """
        current_status = application.status

        # Kiểm tra quy trình chuyển đổi status
        valid_transitions = {
            ApplicationStatus.PENDING: [
                ApplicationStatus.REVIEWING,
                ApplicationStatus.REJECTED,
            ],
            ApplicationStatus.REVIEWING: [
                ApplicationStatus.ACCEPTED,
                ApplicationStatus.REJECTED,
            ],
            ApplicationStatus.ACCEPTED: [],  # Cannot transition from ACCEPTED to other statuses
            ApplicationStatus.REJECTED: [],  # Cannot transition from REJECTED to other statuses
        }

        if new_status not in valid_transitions.get(current_status, []):
            valid_status = [
                ApplicationStatus(s).label
                for s in valid_transitions.get(current_status, [])
            ]
            raise ValueError(
                f"Cannot transition from '{ApplicationStatus(current_status).label}' to '{ApplicationStatus(new_status).label}'. "
                f"Valid statuses: {', '.join(valid_status)}"
            )

        # Cập nhật trạng thái
        application.status = new_status
        if note:
            application.note = note
        application.save(update_fields=["status", "note"])

        # Gửi email thông báo cho ứng viên
        JobApplicationService.notify_applicant_status_change(application)

        return application

    @staticmethod
    def notify_applicant_status_change(application):
        """
        Notify applicant when application status changes
        """
        subject = f"Application Status Update: {application.job.title}"
        status_display = ApplicationStatus(application.status).label

        message = f"""
        Dear {application.applicant.username},

        Your application for the position of {application.job.title} at {application.job.company.name} has been updated.

        Current status: {status_display}

        {application.note if application.note else ''}

        You can view the details of your application on your profile page.

        Regards,
        HiRise Team
        """

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[application.applicant.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error sending email: {str(e)}")
