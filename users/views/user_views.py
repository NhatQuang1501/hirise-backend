from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
from django.db import IntegrityError, transaction
from jobs.models import Industry, SkillTag, Location
from users.utils import CustomPagination
from users.models import User, ApplicantProfile, CompanyProfile, CompanyFollower
from users.serializers import (
    UserSerializer,
    ApplicantProfileSerializer,
    CompanyProfileSerializer,
    CompanyFollowerSerializer,
)
from users.choices import Role, Gender
from users.permission import *
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from users.filters import ApplicantFilter, CompanyFilter


class BaseUserView(APIView):
    pagination_class = CustomPagination
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = None
    profile_serializer_class = None
    role = None

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        return User.objects.filter(role=self.role)

    def filter_queryset(self, queryset):
        for backend in self.filter_backends:
            queryset = backend().filter_queryset(self.request, queryset, self)
        return queryset

    def get(self, request):
        queryset = self.get_queryset()
        filtered_queryset = self.filter_queryset(queryset)

        # Luôn bao gồm profile
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(filtered_queryset, request)

        serializer = self.serializer_class(
            paginated_queryset,
            many=True,
            context={"request": request, "include_profile": True},  # Luôn set là True
        )

        return paginator.get_paginated_response(serializer.data)

    def get_profile(self, user):
        raise NotImplementedError("Subclasses must implement get_profile")

    def get_object(self, pk):
        return get_object_or_404(User, pk=pk, role=self.role)

    def retrieve(self, request, pk):
        user = self.get_object(pk)
        serializer = self.serializer_class(
            user,
            context={"request": request, "include_profile": True},  # Luôn set là True
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, pk, partial=False):
        try:
            user = self.get_object(pk)

            # Kiểm tra quyền
            if not request.user.is_staff and user != request.user:
                return Response(
                    {"detail": "You are not allowed to update this profile"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Xử lý dữ liệu user - loại bỏ phone_number vì đây là trường của profile
            user_data = {}
            for field in request.data:
                if field in [
                    "first_name",
                    "last_name",
                    "email",
                ]:  # Đã loại bỏ "phone_number"
                    user_data[field] = request.data[field]

            # Cập nhật user nếu có dữ liệu
            if user_data:
                user_serializer = self.serializer_class(
                    user, data=user_data, partial=True
                )
                if user_serializer.is_valid():
                    user_serializer.save()
                else:
                    return Response(
                        user_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

            # Xử lý dữ liệu profile
            profile_data = {}
            for field in request.data:
                if field not in [
                    "first_name",
                    "last_name",
                    "email",
                ]:  # Đã loại bỏ "phone_number" khỏi điều kiện
                    profile_data[field] = request.data[field]

            # Cập nhật profile nếu có dữ liệu
            if profile_data:
                profile = self.get_profile(user)
                if profile:
                    profile_serializer = self.profile_serializer_class(
                        profile, data=profile_data, partial=True
                    )
                    if profile_serializer.is_valid():
                        profile_serializer.save()
                    else:
                        return Response(
                            profile_serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            # Tạo response đơn giản hóa
            user_info = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_verified": user.is_verified,
                "is_locked": user.is_locked,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            }

            # Lấy thông tin profile của user
            profile = self.get_profile(user)
            if profile:
                if user.role == Role.APPLICANT:
                    profile_info = {
                        "full_name": profile.full_name,
                        "date_of_birth": profile.date_of_birth,
                        "gender": profile.gender,
                        "phone_number": profile.phone_number,
                        "cv": profile.cv.url if profile.cv else None,
                        "description": profile.description,
                    }
                elif user.role == Role.COMPANY:
                    profile_info = {
                        "name": profile.name,
                        "website": profile.website,
                        "logo": profile.logo.url if profile.logo else None,
                        "description": profile.description,
                        "benefits": profile.benefits,
                        "founded_year": profile.founded_year,
                        "locations": [loc.id for loc in profile.locations.all()],
                        "industries": [ind.id for ind in profile.industries.all()],
                        "skills": [skill.id for skill in profile.skills.all()],
                        "location_names": [
                            loc.address for loc in profile.locations.all()
                        ],  # Thay đổi này
                        "industry_names": [
                            ind.name for ind in profile.industries.all()
                        ],
                        "skill_names": [skill.name for skill in profile.skills.all()],
                    }
                else:
                    profile_info = {}

                user_info["profile"] = profile_info

            return Response(user_info)

        except Exception as e:
            return Response(
                {"detail": f"Error editing profile: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ApplicantView(BaseUserView):
    role = Role.APPLICANT
    serializer_class = UserSerializer
    profile_serializer_class = ApplicantProfileSerializer
    filterset_class = ApplicantFilter
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    def get_permissions(self):
        if self.request.method in ["GET"]:
            return [AllowAny()]  # Cho phép xem không cần đăng nhập
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        return (
            User.objects.filter(role=self.role)
            .select_related("applicant_profile")
            .prefetch_related("social_links")
        )

    def get(self, request, pk=None):
        if pk:
            user = self.get_object(pk)
            serializer = self.serializer_class(user)
            return Response(serializer.data)

        queryset = self.get_queryset()
        filtered_queryset = self.filter_queryset(queryset)

        page = self.pagination_class()
        paginated_queryset = page.paginate_queryset(filtered_queryset, request)

        serializer = self.serializer_class(paginated_queryset, many=True)
        return page.get_paginated_response(serializer.data)

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

    def get_profile(self, user):
        return get_object_or_404(ApplicantProfile, user=user)


class CompanyView(BaseUserView):
    role = Role.COMPANY
    serializer_class = UserSerializer
    profile_serializer_class = CompanyProfileSerializer
    filterset_class = CompanyFilter
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    def get_permissions(self):
        if self.request.method in ["GET"]:
            return [AllowAny()]  # Cho phép xem không cần đăng nhập
        return [permission() for permission in self.permission_classes]

    def get_profile(self, user):
        return get_object_or_404(CompanyProfile, user=user)

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

    def get_profile(self, user):
        return get_object_or_404(CompanyProfile, user=user)

    def update(self, request, pk, partial=False):
        try:
            user = self.get_object(pk)

            # Kiểm tra quyền
            if not request.user.is_staff and user != request.user:
                return Response(
                    {"detail": "You are not allowed to update this profile"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Xử lý skills trước khi cập nhật
            if "skills" in request.data:
                skills_data = request.data.pop("skills")
                skill_objects = []

                for skill_name in skills_data:
                    # Tìm skill theo tên hoặc tạo mới nếu chưa tồn tại
                    skill_obj, created = SkillTag.objects.get_or_create(
                        name=skill_name.strip(),
                        defaults={"description": ""},
                    )
                    skill_objects.append(skill_obj)

                # Cập nhật skills cho company profile
                user.company_profile.skills.set(skill_objects)

            # Xử lý industries trước khi cập nhật
            if "industries" in request.data:
                industries_data = request.data.pop("industries")
                industry_objects = []

                for industry_name in industries_data:
                    # Tìm industry theo tên hoặc tạo mới nếu chưa tồn tại
                    industry_obj, created = Industry.objects.get_or_create(
                        name=industry_name.strip(),
                    )
                    industry_objects.append(industry_obj)

                # Cập nhật industries cho company profile
                user.company_profile.industries.set(industry_objects)

            # Xử lý locations trước khi cập nhật
            if "locations" in request.data:
                locations_data = request.data.pop("locations")
                location_objects = []

                for location_address in locations_data:
                    if isinstance(location_address, str):
                        # Nếu là string (địa chỉ) thì tạo mới hoặc tìm theo địa chỉ
                        location_obj, created = Location.objects.get_or_create(
                            address=location_address.strip(),
                            defaults={"country": "Vietnam"},
                        )
                        location_objects.append(location_obj)
                    else:
                        # Nếu là UUID thì tìm theo ID
                        try:
                            location_obj = Location.objects.get(id=location_address)
                            location_objects.append(location_obj)
                        except Location.DoesNotExist:
                            pass

                # Cập nhật locations cho company profile
                user.company_profile.locations.set(location_objects)

            # Xử lý dữ liệu user
            user_data = {}
            for field in request.data:
                if field in ["first_name", "last_name", "email", "phone_number"]:
                    user_data[field] = request.data[field]

            # Cập nhật user nếu có dữ liệu
            if user_data:
                user_serializer = self.serializer_class(
                    user, data=user_data, partial=True
                )
                if user_serializer.is_valid():
                    user_serializer.save()
                else:
                    return Response(
                        user_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

            # Xử lý dữ liệu profile còn lại
            profile_data = {}
            for field in request.data:
                if field not in [
                    "first_name",
                    "last_name",
                    "email",
                    "phone_number",
                    "skills",
                    "industries",
                    "locations",  # Thêm locations vào danh sách loại trừ
                ]:
                    profile_data[field] = request.data[field]

            # Cập nhật profile nếu có dữ liệu
            if profile_data:
                profile = self.get_profile(user)
                if profile:
                    profile_serializer = self.profile_serializer_class(
                        profile, data=profile_data, partial=True
                    )
                    if profile_serializer.is_valid():
                        profile_serializer.save()
                    else:
                        return Response(
                            profile_serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            # Lấy thông tin mới nhất của user và profile
            updated_user = self.get_object(pk)
            serializer = self.serializer_class(
                updated_user,
                context={
                    "request": request,
                    "include_profile": True,
                },
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"detail": f"Error editing profile: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CompanyFollowerView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, company_id=None):
        """
        Lấy danh sách công ty mà ứng viên đang theo dõi hoặc danh sách người theo dõi của một công ty
        """
        user = request.user

        # Nếu là ứng viên, lấy danh sách công ty đang theo dõi
        if user.role == Role.APPLICANT:
            try:
                applicant_profile = user.applicant_profile
                followers = CompanyFollower.objects.filter(applicant=applicant_profile)

                paginator = self.pagination_class()
                paginated_queryset = paginator.paginate_queryset(followers, request)
                serializer = CompanyFollowerSerializer(paginated_queryset, many=True)

                return paginator.get_paginated_response(serializer.data)
            except ApplicantProfile.DoesNotExist:
                return Response(
                    {"detail": "Applicant profile not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Nếu là công ty, lấy danh sách người theo dõi
        elif user.role == Role.COMPANY:
            try:
                company_profile = user.company_profile
                followers = CompanyFollower.objects.filter(company=company_profile)

                paginator = self.pagination_class()
                paginated_queryset = paginator.paginate_queryset(followers, request)
                serializer = CompanyFollowerSerializer(paginated_queryset, many=True)

                return paginator.get_paginated_response(serializer.data)
            except CompanyProfile.DoesNotExist:
                return Response(
                    {"detail": "Company profile not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Nếu là admin, có thể xem tất cả
        elif user.is_staff:
            if company_id:
                company = get_object_or_404(CompanyProfile, user__id=company_id)
                followers = CompanyFollower.objects.filter(company=company)
            else:
                followers = CompanyFollower.objects.all()

            paginator = self.pagination_class()
            paginated_queryset = paginator.paginate_queryset(followers, request)
            serializer = CompanyFollowerSerializer(paginated_queryset, many=True)

            return paginator.get_paginated_response(serializer.data)

        return Response(
            {"detail": "You don't have permission to view this information"},
            status=status.HTTP_403_FORBIDDEN,
        )

    def post(self, request, company_id):
        """
        Ứng viên theo dõi một công ty
        """
        user = request.user

        # Chỉ ứng viên mới có thể theo dõi công ty
        if user.role != Role.APPLICANT:
            return Response(
                {"detail": "Only applicants can follow companies"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            with transaction.atomic():
                applicant_profile = user.applicant_profile
                company = get_object_or_404(CompanyProfile, user__id=company_id)

                # Kiểm tra xem đã follow chưa
                follower, created = CompanyFollower.objects.get_or_create(
                    applicant=applicant_profile, company=company
                )

                if created:
                    # Tăng follower_count
                    company.follower_count += 1
                    company.save(update_fields=["follower_count"])

                    serializer = CompanyFollowerSerializer(follower)
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                else:
                    return Response(
                        {"detail": "You are already following this company"},
                        status=status.HTTP_200_OK,
                    )

        except ApplicantProfile.DoesNotExist:
            return Response(
                {"detail": "Applicant profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def delete(self, request, company_id):
        """
        Ứng viên hủy theo dõi một công ty
        """
        user = request.user

        # Chỉ ứng viên mới có thể hủy theo dõi công ty
        if user.role != Role.APPLICANT:
            return Response(
                {"detail": "Only applicants can unfollow companies"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            with transaction.atomic():
                applicant_profile = user.applicant_profile
                company = get_object_or_404(CompanyProfile, user__id=company_id)

                try:
                    follower = CompanyFollower.objects.get(
                        applicant=applicant_profile, company=company
                    )

                    # Giảm follower_count trước khi xóa
                    company.follower_count = max(0, company.follower_count - 1)
                    company.save(update_fields=["follower_count"])

                    # Xóa bản ghi follower
                    follower.delete()

                    return Response(status=status.HTTP_204_NO_CONTENT)
                except CompanyFollower.DoesNotExist:
                    return Response(
                        {"detail": "You are not following this company"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
        except ApplicantProfile.DoesNotExist:
            return Response(
                {"detail": "Applicant profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class CheckFollowStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        """
        Kiểm tra xem ứng viên có đang theo dõi công ty không
        """
        user = request.user

        if user.role != Role.APPLICANT:
            return Response(
                {"detail": "Only applicants can check follow status"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            applicant_profile = user.applicant_profile
            company = get_object_or_404(CompanyProfile, user__id=company_id)

            is_following = CompanyFollower.objects.filter(
                applicant=applicant_profile, company=company
            ).exists()

            return Response({"is_following": is_following})
        except ApplicantProfile.DoesNotExist:
            return Response(
                {"detail": "Applicant profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
