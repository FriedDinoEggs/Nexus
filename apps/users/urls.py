from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    # TokenRefreshView,
)

from .views import CustomJWTLogoutView, CustomTokenRefreshView, UserProfileViewSet, UserRegisterView

router = DefaultRouter()
router.register(r'', UserProfileViewSet, basename='users')
urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('logout/', CustomJWTLogoutView.as_view(), name='logout'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='refresh'),
    path('register/', UserRegisterView.as_view(), name='register'),
]

urlpatterns += router.urls
