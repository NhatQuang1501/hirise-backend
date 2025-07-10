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

# Constants for OTP
OTP_LENGTH = 6
EMAIL_SUPPORT = "quangpbl1@gmail.com"
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

    subject = "Account Verification - HiRise"
    body = (
        f"Dear {user.username},\n\n"
        f"Thank you for registering an account at HiRise. To complete your registration, please enter the OTP code below:\n\n"
        f"{otp}\n\n"
        f"This OTP code is valid for {settings.OTP_EXPIRY_TIME // 60} minutes. If the code expires, please request a new OTP from the system.\n\n"
        "If you did not make this request, please ignore this email.\n\n"
        "Thank you for your trust and for using HiRise services. We are always here to support you.\n\n"
        "If you need assistance, please contact us:\n"
        f"  - Support email: {EMAIL_SUPPORT}\n"
        f"  - Hotline: {HOTLINE}\n\n"
        "Best regards,\n"
        "HiRise Management Team"
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
        f"Dear {user.username},\n\n"
        f"{body_content}\n\n"
        "If you need assistance, please contact us:\n"
        f"  - Support email: {EMAIL_SUPPORT}\n"
        f"  - Hotline: {HOTLINE}\n\n"
        "Best regards,\n"
        "HiRise Management Team"
    )


def send_email_account_lock(user, locked_reason, locked_date, unlocked_date):
    """Gửi email thông báo khóa tài khoản"""
    subject = "Account Locked Notification - HiRise"
    body_content = (
        f"We regret to inform you that your account on the HiRise system has been locked due to the following reason: {locked_reason}. This action was taken to ensure the security of your account and the system.\n\n"
        f"Your account has been locked from {locked_date.strftime('%H:%M:%S %d/%m/%Y')} to {unlocked_date.strftime('%H:%M:%S %d/%m/%Y')}.\n\n"
        "During the lock period, you will not be able to log in or use the system's functions. "
        "We sincerely apologize if this causes you any inconvenience.\n\n"
        "If you believe this is an error or if you have any questions, please contact us for assistance.\n\n"
        "Thank you for your understanding and cooperation.\n\n"
    )

    body = _create_email_template(user, subject, body_content)
    send_email_async(user, subject, body)


def send_email_account_unlock(user, unlocked_date):
    """Gửi email thông báo mở khóa tài khoản"""
    subject = "Account Unlocked Notification - HiRise"
    body_content = (
        f"Your account on the HiRise system has been unlocked from {unlocked_date.strftime('%H:%M:%S %d/%m/%Y')}.\n\n"
        "You can log in and use the system's functions as usual. "
        "Thank you for being with HiRise.\n\n"
    )

    body = _create_email_template(user, subject, body_content)
    send_email_async(user, subject, body)


class CustomPagination(PageNumberPagination):
    page_size = 10  # Number of items per page
    page_size_query_param = (
        "page_size"  # Allow clients to change page_size via query param
    )
    max_page_size = 50  # Maximum limit for page_size

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,  # Total number of items
                "next": self.get_next_link(),  # Link to next page
                "previous": self.get_previous_link(),  # Link to previous page
                "current_page": self.page.number,  # Current page
                "total_pages": self.page.paginator.num_pages,  # Total number of pages
                "data": data,  # Data for current page
            },
            status=status.HTTP_200_OK,
        )
