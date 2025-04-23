from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q

from users.serializers import (
    UserSerializer,
    ApplicantProfileSerializer,
    RecruiterProfileSerializer,
)
from users.models import User, ApplicantProfile, RecruiterProfile
from users.choices import Role
from users.permission import IsOwnerOrAdmin, IsUserProfile
from users.utils import CustomPagination


class UserListView(APIView):
    permission_classes = [AllowAny]
    pagination_class = CustomPagination

    def get(self, request):
        # Get query params
        include_profile = (
            request.query_params.get("include_profile", "false").lower() == "true"
        )
        search = request.query_params.get("search", "")
        role = request.query_params.get("role", "")

        # Get profile specific filters
        gender = request.query_params.get("gender", "")
        company = request.query_params.get("company", "")

        # Base queryset
        queryset = User.objects.all()

        # Apply basic filters
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) | Q(email__icontains=search)
            )

        if role:
            queryset = queryset.filter(role=role)

        # Apply profile specific filters
        if gender:
            if role == Role.APPLICANT:
                applicant_ids = ApplicantProfile.objects.filter(
                    gender=gender
                ).values_list("user_id", flat=True)
                queryset = queryset.filter(id__in=applicant_ids)
            elif role == Role.RECRUITER:
                recruiter_ids = RecruiterProfile.objects.filter(
                    gender=gender
                ).values_list("user_id", flat=True)
                queryset = queryset.filter(id__in=recruiter_ids)

        if company and role == Role.RECRUITER:
            recruiter_ids = RecruiterProfile.objects.filter(
                company__name__icontains=company
            ).values_list("user_id", flat=True)
            queryset = queryset.filter(id__in=recruiter_ids)

        # Apply pagination
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize data with profiles
        serializer = UserSerializer(
            paginated_queryset,
            many=True,
            exclude_profile=not include_profile,
            context={"request": request},
        )

        # Return paginated response with status
        response = paginator.get_paginated_response(serializer.data)
        response.status_code = status.HTTP_200_OK
        return response


class UserDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        user = get_object_or_404(User, id=pk)
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current user's profile"""
        user = request.user
        if user.role == Role.ADMIN:
            return Response(
                {"message": "Admin doesn't have profile"},
                status=status.HTTP_404_NOT_FOUND,
            )

        profile = None
        if user.role == Role.APPLICANT:
            profile = get_object_or_404(ApplicantProfile, user=user)
            serializer = ApplicantProfileSerializer(profile)
        else:
            profile = get_object_or_404(RecruiterProfile, user=user)
            serializer = RecruiterProfileSerializer(profile)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        """Update full profile"""
        user = request.user
        if user.role == Role.ADMIN:
            return Response(
                {"error": "Admin doesn't have profile to update"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = None
        serializer = None
        if user.role == Role.APPLICANT:
            profile = get_object_or_404(ApplicantProfile, user=user)
            serializer = ApplicantProfileSerializer(profile, data=request.data)
        else:
            profile = get_object_or_404(RecruiterProfile, user=user)
            serializer = RecruiterProfileSerializer(profile, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """Update partial profile"""
        user = request.user
        if user.role == Role.ADMIN:
            return Response(
                {"error": "Admin doesn't have profile to update"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = None
        serializer = None
        if user.role == Role.APPLICANT:
            profile = get_object_or_404(ApplicantProfile, user=user)
            serializer = ApplicantProfileSerializer(
                profile, data=request.data, partial=True
            )
        else:
            profile = get_object_or_404(RecruiterProfile, user=user)
            serializer = RecruiterProfileSerializer(
                profile, data=request.data, partial=True
            )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
