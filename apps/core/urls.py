from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.core.views import health

router = DefaultRouter

urlpatterns = [
    path('health/', health.as_view(), name='health'),
]
