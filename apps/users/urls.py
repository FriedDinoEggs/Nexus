from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import UserProfileViewSet, UserRegisterView

router = DefaultRouter()
router.register(r'', UserProfileViewSet, basename='users')
urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('logout/', TokenBlacklistView.as_view(), name='logout'),
    path('refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('register/', UserRegisterView.as_view(), name='register'),
]

urlpatterns += router.urls
