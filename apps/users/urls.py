from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView

from .views import (
    CustomJWTLogoutView,
    CustomTokenRefreshView,
    GoogleLoginViewSet,
    UserProfileViewSet,
    UserRegisterView,
    UserResetPasswordViewSet,
    UserVerificationViewSet,
)

router = DefaultRouter()
# router = root_router
router.register(r'users', UserProfileViewSet, basename='users')
router.register(r'verification', UserVerificationViewSet, basename='email-verification')
router.register(r'password-reset', UserResetPasswordViewSet, basename='password-reset')

urlpatterns = [
    path('users/login/', TokenObtainPairView.as_view(), name='login'),
    path('users/login/google/', GoogleLoginViewSet.as_view({'post': 'login'}), name='google-login'),
    path('users/logout/', CustomJWTLogoutView.as_view(), name='logout'),
    path('users/refresh/', CustomTokenRefreshView.as_view(), name='refresh'),
    path('users/register/', UserRegisterView.as_view(), name='register'),
]

urlpatterns += router.urls
