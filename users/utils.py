from datetime import timedelta
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging
import random
import string
from django.core.cache import cache
from threading import Thread

logger = logging.getLogger(__name__)

# Hằng số cho OTP
OTP_LENGTH = 6
EMAIL_SUPPORT = "support@hirise.com"
HOTLINE = "0123 456 789"


def generate_otp():
    """Tạo mã OTP 6 chữ số"""
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def _get_cache_key(email):
    """Tạo cache key từ email"""
    return f"otp_{email.lower()}"


def store_otp_in_cache(email, otp):
    """Lưu OTP vào cache với thời gian hết hạn"""
    cache_key = _get_cache_key(email)
    cache.set(cache_key, otp, timeout=settings.OTP_EXPIRY_TIME)


def get_otp_from_cache(email):
    """Lấy OTP từ cache"""
    cache_key = _get_cache_key(email)
    return cache.get(cache_key)


def delete_otp_from_cache(email):
    """Xóa OTP khỏi cache"""
    cache_key = _get_cache_key(email)
    cache.delete(cache_key)


def get_tokens_for_user(user):
    """Tạo access và refresh token cho user"""
    refresh = RefreshToken.for_user(user)
    # Thêm thông tin bổ sung vào token
    for token in (refresh, refresh.access_token):
        token["role"] = user.role

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def send_email_async(user, subject, body):
    """Gửi email bất đồng bộ"""

    def send():
        EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email],
        ).send()

    Thread(target=send, daemon=True).start()


def create_and_send_otp(user):
    """Tạo OTP, lưu vào cache và gửi email"""
    otp = generate_otp()
    store_otp_in_cache(user.email, otp)

    subject = "Mã xác thực đăng ký tài khoản HiRise"
    body = (
        f"Kính gửi {user.username},\n\n"
        f"Cảm ơn bạn đã đăng ký tài khoản tại HiRise. Để hoàn tất việc đăng ký, vui lòng nhập mã OTP dưới đây:\n\n"
        f"{otp}\n\n"
        f"Mã OTP này có hiệu lực trong vòng {settings.OTP_EXPIRY_TIME // 60} phút. Nếu mã hết hạn, vui lòng yêu cầu gửi lại mã OTP từ hệ thống.\n\n"
        "Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email.\n\n"
        "Xin cảm ơn vì đã tin tưởng và sử dụng dịch vụ của HiRise.\n\n"
        "Trân trọng,\n"
        "Ban Quản Trị HiRise"
    )

    send_email_async(user, subject, body)
    return otp


def token_blacklisted(token):
    """Đưa token vào blacklist"""
    try:
        refresh_token = RefreshToken(token)
        # Kiểm tra xem token đã trong blacklist chưa
        if BlacklistedToken.objects.filter(
            token__jti=refresh_token.payload["jti"]
        ).exists():
            return True

        refresh_token.blacklist()
        return True
    except Exception as e:
        logger.error(f"Token blacklist error: {str(e)}")
        return False


def _create_email_template(user, title, body_content):
    """Tạo template email chung"""
    return (
        f"Kính gửi {user.username},\n\n"
        f"{body_content}\n\n"
        f"Nếu bạn cần hỗ trợ, vui lòng liên hệ:\n"
        f"  - Email hỗ trợ: {EMAIL_SUPPORT}\n"
        f"  - Hotline: {HOTLINE}\n\n"
        "Trân trọng,\n"
        "Ban Quản Trị HiRise"
    )


def send_email_account_lock(user, locked_reason, locked_date, unlocked_date):
    """Gửi email thông báo khóa tài khoản"""
    subject = "Thông báo: Tài khoản của bạn trên HiRise đã bị khóa"

    body_content = (
        f"Chúng tôi xin thông báo rằng tài khoản của bạn trên hệ thống HiRise đã bị khóa với lý do sau: {locked_reason}\n\n"
        f"Tài khoản của bạn bị khoá trong khoảng thời gian: {locked_date.strftime('%H:%M:%S ngày %d/%m/%Y')} - {unlocked_date.strftime('%H:%M:%S ngày %d/%m/%Y')}.\n\n"
        "Trong thời gian tài khoản bị khóa, bạn sẽ không thể đăng nhập hoặc sử dụng các chức năng của hệ thống. "
        "Chúng tôi chân thành xin lỗi nếu điều này gây bất tiện cho bạn."
    )

    body = _create_email_template(user, subject, body_content)
    send_email_async(user, subject, body)


def send_email_account_unlock(user, unlocked_date):
    """Gửi email thông báo mở khóa tài khoản"""
    subject = "Thông báo: Tài khoản của bạn trên HiRise đã được mở khóa"

    body_content = (
        f"Chúng tôi xin thông báo rằng tài khoản của bạn trên hệ thống HiRise đã được mở khóa từ {unlocked_date.strftime('%H:%M:%S ngày %d/%m/%Y')}.\n\n"
        "Bạn có thể đăng nhập và sử dụng các chức năng của hệ thống như bình thường. "
        "Cảm ơn bạn đã đồng hành cùng HiRise."
    )

    body = _create_email_template(user, subject, body_content)
    send_email_async(user, subject, body)


class CustomPagination(PageNumberPagination):
    page_size = 10  # Số lượng items trên mỗi trang
    page_size_query_param = (
        "page_size"  # Cho phép client thay đổi page_size qua query param
    )
    max_page_size = 100  # Giới hạn tối đa của page_size

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,  # Tổng số items
                "next": self.get_next_link(),  # Link trang tiếp theo
                "previous": self.get_previous_link(),  # Link trang trước
                "current_page": self.page.number,  # Trang hiện tại
                "total_pages": self.page.paginator.num_pages,  # Tổng số trang
                "results": data,  # Dữ liệu của trang hiện tại
            },
            status=status.HTTP_200_OK,
        )
