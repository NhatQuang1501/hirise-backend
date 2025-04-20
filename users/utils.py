from datetime import timedelta
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from django.core.mail import EmailMultiAlternatives
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from users.models import User
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
import logging
import random
import string
from django.core.cache import cache
from threading import Thread

logger = logging.getLogger(__name__)


def generate_otp():
    """Tạo mã OTP 6 chữ số"""
    return "".join(random.choices(string.digits, k=6))


def store_otp_in_cache(email, otp):
    """Lưu OTP vào cache với thời gian hết hạn"""
    cache_key = f"otp_{email}"
    cache.set(cache_key, otp, timeout=settings.OTP_EXPIRY_TIME)


def get_otp_from_cache(email):
    """Lấy OTP từ cache"""
    cache_key = f"otp_{email}"
    return cache.get(cache_key)


def delete_otp_from_cache(email):
    """Xóa OTP khỏi cache"""
    cache_key = f"otp_{email}"
    cache.delete(cache_key)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role

    access_token = refresh.access_token
    access_token["role"] = user.role
    return {
        "refresh": str(refresh),
        "access": str(access_token),
    }


def send_email_async(user, subject, body):
    def send():
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email],
        )
        email.send()

    Thread(target=send).start()


def create_and_send_otp(user):
    """Tạo OTP, lưu vào cache và gửi email"""
    otp = generate_otp()
    store_otp_in_cache(user.email, otp)

    subject = "Mã xác thực đăng ký tài khoản HiRise"
    body = (
        f"Kính gửi {user.username},\n\n"
        f"Cảm ơn bạn đã đăng ký tài khoản tại HiRise. Để hoàn tất việc đăng ký, vui lòng nhập mã OTP dưới đây:\n\n"
        f"{otp}\n\n"
        "Mã OTP này có hiệu lực trong vòng 10 phút. Nếu mã hết hạn, vui lòng yêu cầu gửi lại mã OTP từ hệ thống.\n\n"
        "Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email.\n\n"
        "Xin cảm ơn vì đã tin tưởng và sử dụng dịch vụ của HiRise.\n\n"
        "Trân trọng,\n"
        "Ban Quản Trị HiRise"
    )

    send_email_async(user, subject, body)

    return otp


def decode_token(token):
    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        return validated_token.get("user_id")

    except Exception as e:
        logger.error(f"Token decode error: {str(e)}")
        return None


def token_blacklisted(token):
    try:
        refresh_token = RefreshToken(token)

        if BlacklistedToken.objects.filter(
            token__jti=refresh_token.payload["jti"]
        ).exists():
            return True

        try:
            refresh_token.blacklist()
            return True
        except Exception as e:
            logger.error(f"Error blacklisting token: {str(e)}")
            return False

    except Exception as e:
        logger.error(f"Invalid token error: {str(e)}")
        return False


def send_email_account_lock(user, locked_reason, locked_date, unlocked_date):
    subject = "Thông báo: Tài khoản của bạn trên HiRise đã bị khóa"

    body = (
        f"Kính gửi {user.username},\n\n"
        f"Chúng tôi xin thông báo rằng tài khoản của bạn trên hệ thống HiRise đã bị khóa với lý do sau: {locked_reason}\n\n"
        f"Tài khoản của bạn bị khoá trong khoảng thời gian: {locked_date.strftime('%H:%M:%S ngày %d/%m/%Y')} - {unlocked_date.strftime('%H:%M:%S ngày %d/%m/%Y')}.\n\n"
        "Trong thời gian tài khoản bị khóa, bạn sẽ không thể đăng nhập hoặc sử dụng các chức năng của hệ thống. "
        "Nếu bạn cần hỗ trợ hoặc muốn khiếu nại về quyết định này, vui lòng liên hệ với chúng tôi qua email hoặc hotline dưới đây:\n\n"
        "  - Email hỗ trợ: support@hirise.com\n"
        "  - Hotline: 0123 456 789\n\n"
        "Chúng tôi chân thành xin lỗi nếu điều này gây bất tiện cho bạn và cảm ơn bạn đã đồng hành cùng HiRise.\n\n"
        "Trân trọng,\n"
        "Ban Quản Trị HiRise"
    )

    send_email_async(user, subject, body)


def send_email_account_unlock(user, unlocked_date):
    subject = "Thông báo: Tài khoản của bạn trên HiRise đã được mở khóa"

    body = (
        f"Kính gửi {user.username},\n\n"
        f"Chúng tôi xin thông báo rằng tài khoản của bạn trên hệ thống HiRise đã được mở khóa từ {unlocked_date.strftime('%H:%M:%S ngày %d/%m/%Y')}.\n\n"
        "Bạn có thể đăng nhập và sử dụng các chức năng của hệ thống như bình thường. "
        "Nếu bạn có bất kỳ câu hỏi hoặc cần hỗ trợ, vui lòng liên hệ với chúng tôi qua email hoặc hotline dưới đây:\n\n"
        "  - Email hỗ trợ: support@hirise.com\n"
        "  - Hotline: 0123 456 789\n\n"
        "Cảm ơn bạn đã đồng hành cùng HiRise.\n\n"
        "Trân trọng,\n"
        "Ban Quản Trị HiRise"
    )

    send_email_async(user, subject, body)
