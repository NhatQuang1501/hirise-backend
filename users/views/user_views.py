from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
from users.utils import CustomPagination
from users.models import User, ApplicantProfile, RecruiterProfile
from users.serializers import (
    UserSerializer,
    ApplicantProfileSerializer,
    RecruiterProfileSerializer,
)
from users.choices import Role, Gender
from users.permission import *
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from users.filters import ApplicantFilter, RecruiterFilter


class BaseUserView(APIView):
    pagination_class = CustomPagination
    serializer_class = UserSerializer
    filter_backends = DjangoFilterBackend
    filterset_class = None
    profile_serializer_class = None
    role = None

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        """Base queryset"""
        return User.objects.filter(role=self.role)

    def filter_queryset(self, queryset):
        """Apply filtering backend"""
        for backend in list(self.filter_backends):
            queryset = backend().filter_queryset(self.request, queryset, self)
        return queryset

    def get(self, request):
        """List users with pagination"""
        queryset = self.get_queryset()
        filtered_queryset = self.filter_queryset(queryset)

        include_profile = (
            request.query_params.get("include_profile", "false").lower() == "true"
        )

        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(filtered_queryset, request)

        serializer = self.serializer_class(
            paginated_queryset,
            many=True,
            exclude_profile=not include_profile,
            context={"request": request},
        )

        return paginator.get_paginated_response(serializer.data)

    def get_profile(self, user):
        """Get profile for specific user"""
        raise NotImplementedError("Subclasses must implement get_profile")

    def get_object(self, pk):
        """Get specific user by primary key"""
        return get_object_or_404(User, pk=pk, role=self.role)

    def retrieve(self, request, pk):
        """Get user detail with profile"""
        user = self.get_object(pk)
        serializer = self.serializer_class(
            user, exclude_profile=False, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update_profile(self, profile, data, partial=False):
        """Update profile with validation"""
        serializer = self.profile_serializer_class(profile, data=data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk, partial=False):
        """Update user profile"""
        user = self.get_object(pk)
        profile = self.get_profile(user)

        # Check if user is owner
        if request.user.id != user.id:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return self.update_profile(profile, request.data, partial=partial)


class ApplicantView(BaseUserView):
    role = Role.APPLICANT
    profile_serializer_class = ApplicantProfileSerializer
    filterset_class = ApplicantFilter
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        """Handle both list and detail views"""
        if pk:
            return self.retrieve(request, pk)
        return super().get(request)

    def put(self, request, pk=None):
        """Handle profile update"""
        if not pk:
            return Response(
                {"detail": "Profile ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        return self.update(request, pk)

    def patch(self, request, pk=None):
        """Handle partial profile update"""
        if not pk:
            return Response(
                {"detail": "Profile ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        return self.update(request, pk, partial=True)


class RecruiterView(BaseUserView):
    role = Role.RECRUITER
    profile_serializer_class = RecruiterProfileSerializer
    filterset_class = RecruiterFilter
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            return self.retrieve(request, pk)
        return super().get(request)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"detail": "Profile ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        return self.update(request, pk)

    def patch(self, request, pk=None):
        if not pk:
            return Response(
                {"detail": "Profile ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        return self.update(request, pk, partial=True)
