from django.contrib.auth import get_user_model
from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from .permissions import IsEventManagerGroup, IsOwnerObject, IsSuperAdminGroup
from .serializers import UserProfileSerializer, UserRegistrationSerializer

# Create your views here.
User = get_user_model()


class UserRegisterView(generics.CreateAPIView):
    queryset = User.objects.none()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    authentication_classes = [JWTAuthentication]

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
        new_email = f'{instance.email}.deleted.{instance.pk}'
        if len(new_email) > 254:
            new_email = new_email[:254]
        instance.email = new_email
        instance.save()
