from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class CoreSmokeTests(APITestCase):
    def test_health_get_returns_200(self):
        response = self.client.get(reverse('v1:core_app:health'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_head_returns_200(self):
        response = self.client.head(reverse('v1:core_app:health'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_schema_endpoint_returns_openapi_document(self):
        response = self.client.get(reverse('schema'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['openapi'], '3.0.3')
        self.assertIn('/api/v1/health/', response.data['paths'])

    def test_swagger_ui_endpoint_returns_200(self):
        response = self.client.get(reverse('swagger-ui'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'SwaggerUIBundle')
