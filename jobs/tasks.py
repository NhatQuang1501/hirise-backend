from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import Job, JobApplication
from users.choices import JobStatus, ApplicationStatus


@shared_task
def close_expired_jobs():
    """
    Tự động đóng các job đã hết hạn (closed_date đã qua)
    """
    today = timezone.now().date()

    # Tìm các job đã hết hạn nhưng vẫn đang mở
    expired_jobs = Job.objects.filter(status=JobStatus.PUBLISHED, closed_date__lt=today)

    count = 0
    for job in expired_jobs:
        try:
            from .services import JobService

            JobService.close_job(job, reason="Hết hạn tự động")
            count += 1
        except Exception as e:
            print(f"Lỗi khi đóng job {job.id}: {str(e)}")

    return f"Đã đóng {count} job hết hạn"


@shared_task
def notify_pending_applications():
    """
    Thông báo cho nhà tuyển dụng về các đơn ứng tuyển đang chờ xử lý
    """
    # Tìm các đơn ứng tuyển đã chờ quá 3 ngày
    three_days_ago = timezone.now() - timedelta(days=3)

    pending_applications = JobApplication.objects.filter(
        status=ApplicationStatus.PENDING, created_at__lt=three_days_ago
    ).select_related("job", "job__company", "applicant")

    # Nhóm các đơn theo công ty
    company_applications = {}
    for application in pending_applications:
        company = application.job.company
        if company.id not in company_applications:
            company_applications[company.id] = {"company": company, "applications": []}
        company_applications[company.id]["applications"].append(application)

    # Gửi email thông báo cho từng công ty
    for company_data in company_applications.values():
        company = company_data["company"]
        applications = company_data["applications"]

        try:
            from django.core.mail import send_mail
            from django.conf import settings

            subject = f"Thông báo: {len(applications)} đơn ứng tuyển chưa xử lý"
            message = f"""
            Kính gửi {company.name},
            
            Hiện có {len(applications)} đơn ứng tuyển đang chờ xử lý quá 3 ngày:
            
            """

            for app in applications:
                message += f"- {app.applicant.username} ứng tuyển vào vị trí {app.job.title} vào ngày {app.created_at.strftime('%d/%m/%Y')}\n"

            message += """
            Hãy đăng nhập vào hệ thống để xem và xử lý các đơn ứng tuyển.
            
            Trân trọng,
            Đội ngũ HiRise
            """

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[company.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Lỗi khi gửi thông báo đến công ty {company.name}: {str(e)}")

    return f"Đã gửi thông báo cho {len(company_applications)} công ty"


@shared_task
def generate_job_recommendations(user_id):
    """
    Tạo các đề xuất job phù hợp với người dùng
    """
    from users.models import User
    from django.db.models import Count

    try:
        user = User.objects.get(id=user_id)

        # Lấy các job mà người dùng đã ứng tuyển
        applied_jobs = JobApplication.objects.filter(applicant=user).values_list(
            "job_id", flat=True
        )

        # Lấy các kỹ năng từ các job đã ứng tuyển
        applied_job_skills = Job.objects.filter(id__in=applied_jobs).values_list(
            "company__skills__id", flat=True
        )

        # Tìm các job phù hợp dựa trên kỹ năng
        recommendations = (
            Job.objects.filter(
                status=JobStatus.PUBLISHED, company__skills__id__in=applied_job_skills
            )
            .exclude(id__in=applied_jobs)
            .annotate(
                matching_skills=Count(
                    "company__skills__id",
                    filter=Q(company__skills__id__in=applied_job_skills),
                )
            )
            .order_by("-matching_skills")[:10]
        )

        # TODO: Lưu các đề xuất vào cache hoặc database
        # ...

        return (
            f"Đã tạo {recommendations.count()} đề xuất cho người dùng {user.username}"
        )
    except User.DoesNotExist:
        return f"Không tìm thấy người dùng với id {user_id}"
