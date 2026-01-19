import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from apps.users.throttles import ResetPasswordThrottle

from .authentication import CustomJWTAuthentication
from .permissions import IsEventManagerGroup, IsOwnerObject, IsSuperAdminGroup
from .serializers import (
    GoogleLoginSerializer,
    MyToeknRefreshSerializer,
    UserPasswordResetSerializer,
    UserPasswordResetVerifySerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)
from .services import BlackListService, UserVerificationServices

# Create your views here.
User = get_user_model()

logger = logging.getLogger(__name__)


@extend_schema(tags=['v1', 'Users'])
class UserRegisterView(generics.CreateAPIView):
    queryset = User.objects.none()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]


@extend_schema(tags=['v1', 'Users'])
class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base_queryset = User.objects.all().prefetch_related('groups')

        user_group_name = user.groups.values_list('name', flat=True)

        if 'SuperAdmin' in user_group_name:
            return base_queryset
        elif 'EventManager' in user_group_name:
            return base_queryset.filter(Q(is_active=True) | Q(email__endswith='@shadow.com'))
        elif 'Member' in user_group_name:
            return base_queryset.filter(is_active=True)
        return base_queryset.filter(id=user.id)

    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [IsAuthenticated, (IsSuperAdminGroup | IsEventManagerGroup)]
        elif self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            permission_classes = [
                IsAuthenticated,
                (IsSuperAdminGroup | IsEventManagerGroup | IsOwnerObject),
            ]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            serializer_class = UserRegistrationSerializer
        else:
            serializer_class = super().get_serializer_class()
        return serializer_class

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if data.get('email', None) is None:
            import uuid6

            id = uuid6.uuid7()
            email = f'{id}@shadow.com'
            password = 'teampassword'
            data['email'] = email
            data['password'] = password
            data['password_confirm'] = password
            data['is_active'] = False
        else:
            if data.get('is_active', None) == 'False':
                data['is_active'] = False
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_destroy(self, instance):
        instance.is_active = False
        suffix = f'.deleted.{instance.pk}'
        new_email = (instance.email[: 254 - len(suffix)] + suffix)[:254]
        instance.email = new_email
        instance.save()


class UserEmailVerificationViewSet(viewsets.ViewSet):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    lookup_url_kwarg = 'id'

    def get_permissions(self):
        if self.action == 'retrieve':
            return [AllowAny()]
        return super().get_permissions()

    def create(self, request):
        base_url = f'{request.scheme}://{request.get_host()}'

        try:
            UserVerificationServices.send_verification_mail(user=request.user, base_url=base_url)
        except RuntimeError as e:
            return Response(
                {
                    'detail': str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_200_OK)

    def retrieve(self, request, id=None):
        if UserVerificationServices.verify_mail(token=id):
            return Response(status=status.HTTP_200_OK)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class UserResetPasswordView(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = UserPasswordResetSerializer
    throttle_classes = [ResetPasswordThrottle]
    lookup_url_kwarg = 'id'

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            UserVerificationServices.send_reset_pwd_mail(account=serializer.validated_data['email'])
        except Exception as e:
            return Response(data={'detail': {str(e)}}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            data={'detail': 'verification code has been sent'}, status=status.HTTP_202_ACCEPTED
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='verify',
        serializer_class=UserPasswordResetVerifySerializer,
        throttle_classes=[ResetPasswordThrottle],
    )
    def verify(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = User.objects.get(email=serializer.validated_data['email'])
                user.set_password(serializer.validated_data['password'])
                user.save()

            return Response(
                {'message': 'password reset successful'},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({'error': {str(e)}}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['v1', 'Users'])
class GoogleLoginViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = GoogleLoginSerializer
    lookup_url_kwarg = 'id'

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'full_name': user.full_name,
                },
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=['v1', 'users'])
class CustomJWTLogoutView(TokenBlacklistView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def post(self, request, *args, **kwargs):
        access_token = request.auth
        if access_token is not None:
            BlackListService.set_blacklisted(token=access_token, user=request.user)

        return super().post(request, *args, **kwargs)


class IPBaseThrottle(SimpleRateThrottle):
    scope = 'refresh'

    def get_cache_key(self, request, view):
        try:
            token = RefreshToken(request.data.get('refresh'))
            user_id = token.get('user_id')
            return f'throttle_refresh_{user_id}'
        except Exception as e:
            logger.debug(f'Could not extract user_id from refresh token: {e}')
            return f'throttle_refresh_{self.get_ident(request)}'


@extend_schema(tags=['v1', 'Users'])
class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = MyToeknRefreshSerializer
    throttle_classes = [IPBaseThrottle]
