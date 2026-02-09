"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'api/v1/',
        include(
            (
                [
                    path('', include(('apps.users.urls', 'users_app'), namespace='users_app')),
                    path('', include(('apps.events.urls', 'events_app'), namespace='events_app')),
                    path('', include(('apps.teams.urls', 'teams_app'), namespace='teams_app')),
                    path(
                        '', include(('apps.matches.urls', 'matches_app'), namespace='matches_app')
                    ),
                    path('', include(('apps.core.urls', 'core_app'), namespace='core_app')),
                ],
                'v1',
            ),
            namespace='v1',
        ),
    ),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/schema/swagger-ui/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
]


if settings.DEBUG:

    class GoogleLoginView(TemplateView):
        template_name = 'google_index.html'

        def dispatch(self, request, *args, **kwargs):
            response = super().dispatch(request, *args, **kwargs)
            response['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
            return response

    urlpatterns += [
        path('test-google-login/', GoogleLoginView.as_view()),
    ]
