import logging

from django.contrib.auth import get_user_model
from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from .authentication import CustomJWTAuthentication
from .permissions import IsEventManagerGroup, IsOwnerObject, IsSuperAdminGroup
from .serializers import UserProfileSerializer, UserRegistrationSerializer
from .services import BlackListService

# Create your views here.
User = get_user_model()

logger = logging.getLogger(__name__)


class UserRegisterView(generics.CreateAPIView):
    queryset = User.objects.none()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    # authentication_classes = [JWTAuthentication]
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

    def perform_destroy(self, instance):
        instance.is_active = False
        suffix = f'.deleted.{instance.pk}'
        new_email = (instance.email[: 254 - len(suffix)] + suffix)[:254]
        instance.email = new_email
        instance.save()


# class UniversalLogoutView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         authenticator = request.successful_authenticator

#         if isinstance(authenticator, CustomJWTAuthentication):
#             view = CustomJWTLogoutView()
#             view.request = request
#             view.args = args
#             view.kwargs = kwarg
#             return view.post(request, *args, **kwargs)
#         else:
#             pass


class CustomJWTLogoutView(TokenBlacklistView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access_token = request.auth
            BlackListService.set_blacklisted(token=access_token, user=request.user)

        return response


class IPBaseThrottle(SimpleRateThrottle):
    scope = 'refresh'

    def get_cache_key(self, request, view):
        try:
            token = RefreshToken(request.data.get('refresh'))
            user_id = token.get('user_id')
            return f'throttle_refresh_{user_id}'
        except:
            return f'throttle_refresh_{self.get_ident(request)}'


class CustomTokenRefreshView(TokenRefreshView):
    throttle_classes = [IPBaseThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        return response
