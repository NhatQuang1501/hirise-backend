from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from .enums import *
import uuid


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(max_length=100, unique=True)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=64)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.USER,
    )

    is_verified = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    locked_reason = models.TextField(blank=True, null=True)
    locked_date = models.DateTimeField(blank=True, null=True)
    unlocked_date = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    full_name = models.CharField(max_length=100, blank=True, null=True)
