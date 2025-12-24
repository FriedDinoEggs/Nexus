import logging

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from .authentication import CustomJWTAuthentication
from .permissions import IsEventManagerGroup, IsOwnerObject, IsSuperAdminGroup
from .serializers import MyToeknRefreshSerializer, UserProfileSerializer, UserRegistrationSerializer
from .services import BlackListService

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
    serializer_class = UserProfileSerializer
    authentication_classes = [CustomJWTAuthentication]

    def get_queryset(self):
        user = self.request.user
        base_queryset = User.objects.prefetch_related('groups')

        if not user.is_authenticated:
            return User.objects.none()

        user_group_name = user.groups.values_list('name', flat=True)

        if 'SuperAdmin' in user_group_name:
            return base_queryset
        elif 'EventManager' in user_group_name:
            return base_queryset.filter(is_active=True)
        elif 'Member' in user_group_name:
            return base_queryset.filter(id=user.id)
        return base_queryset.filter(id=user.id)

    def get_permissions(self):
        permission_classes = [IsAuthenticated]  # 預設行為

        if self.action in ['create', 'list']:
            permission_classes = [IsAuthenticated, (IsSuperAdminGroup | IsEventManagerGroup)]
        elif self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            permission_classes = [
                IsAuthenticated,
                (IsSuperAdminGroup | IsEventManagerGroup | IsOwnerObject),
            ]

        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        instance.is_active = False
        suffix = f'.deleted.{instance.pk}'
        new_email = (instance.email[: 254 - len(suffix)] + suffix)[:254]
        instance.email = new_email
        instance.save()


@extend_schema(tags=['v1', 'Users'])
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
