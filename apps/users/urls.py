from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView

from .views import (
    CustomJWTLogoutView,
    CustomTokenRefreshView,
    UserEmailVerificationViewSet,
    UserProfileViewSet,
    UserRegisterView,
    UserResetPasswordView,
)

router = DefaultRouter()
router.register(r'user', UserProfileViewSet, basename='users')
router.register(r'verification', UserEmailVerificationViewSet, basename='verification')
router.register(r'password-reset', UserResetPasswordView, basename='password-reset')
urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('logout/', CustomJWTLogoutView.as_view(), name='logout'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='refresh'),
    path('register/', UserRegisterView.as_view(), name='register'),
]

urlpatterns += router.urls
