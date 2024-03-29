from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin
from rest_framework.filters import SearchFilter
from rest_framework.exceptions import AuthenticationFailed, ParseError
from rest_framework_simplejwt.tokens import AccessToken

from .models import USERS_ROLES
from .serializers import UserSerializer, UserCrateSerializer
from .permissions import IsAdminOrSuperuser
from reviews.models import User


@api_view(["POST"])
@permission_classes([AllowAny])
def get_token(request):
    username = request.data.get("username")
    code = request.data.get("confirmation_code")
    if not username:
        return Response(
            data={"username": "Поле некорректно или отсутствует!"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = get_object_or_404(User, username=username)
    if not code or code != user.confirmation_code:
        return Response(
            data={"confirmation_code": "Поле некорректно или отсутствует!"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        data={"token": str(AccessToken.for_user(user))},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def get_confirmation_code(request):
    serializer = UserCrateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    username = serializer.data["username"]
    email = serializer.data["email"]
    try:
        user, _ = User.objects.get_or_create(
            username=username, email=email
        )
    except (IntegrityError, ValidationError):
        raise serializers.ValidationError(
            "Пользователь с такими данными уже существует"
        )
    user.create_confirmation_code()
    send_mail(
        subject="Код подтверждения",
        message=user.confirmation_code,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
    )
    return Response(
        serializer.data,
        status=status.HTTP_200_OK,
    )


class AdminViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = "username"
    filter_backends = (SearchFilter,)
    permission_classes = (IsAdminOrSuperuser,)
    search_fields = ("username",)

    def perform_create(self, serializer):
        if "role" in self.request.data:
            users_roles = [role for role, _ in USERS_ROLES]
            if self.request.data["role"] not in users_roles:
                raise ParseError("Такая роль не предусмотрена!")
            serializer.save(role=self.request.data["role"])
        else:
            serializer.save()

    def perform_update(self, serializer):
        if "role" in self.request.data:
            users_roles = [role for role, _ in USERS_ROLES]
            if self.request.data["role"] not in users_roles:
                raise ParseError("Такая роль не предусмотрена!")
            serializer.save(role=self.request.data["role"])
        else:
            serializer.save()

    def update(self, request, *args, **kwargs):
        if "partial" not in kwargs:
            self.http_method_not_allowed(request, *args, **kwargs)
        return super().update(request, *args, **kwargs)


class UserViewSet(RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    serializer_class = UserSerializer

    def get_object(self):
        user = self.request.user
        if user.is_anonymous:
            raise AuthenticationFailed(
                "Доступно только авторизованным пользователям!"
            )
        return user
