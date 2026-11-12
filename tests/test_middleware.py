from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from django_allauth_cross_domain.models import AccessToken
from django_allauth_cross_domain.middleware import BearerTokenMiddleware


class BearerTokenMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="mw-user", email="mw@example.com", password="password"
        )
        self.middleware = BearerTokenMiddleware(lambda req: HttpResponse(req.user.get_username()))

    def test_valid_bearer_token_sets_request_user(self):
        _, raw_token = AccessToken.issue(self.user, timedelta(minutes=10))
        request = self.factory.get("/any/endpoint", HTTP_AUTHORIZATION=f"Bearer {raw_token}")
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.user, self.user)

    def test_invalid_bearer_token_leaves_anonymous_user(self):
        request = self.factory.get("/any/endpoint", HTTP_AUTHORIZATION="Bearer invalid-token")
        request.user = AnonymousUser()
        self.middleware(request)
        self.assertTrue(request.user.is_anonymous)

    def test_malformed_bearer_header_leaves_anonymous_user(self):
        request = self.factory.get("/any/endpoint", HTTP_AUTHORIZATION="Bearer ")
        request.user = AnonymousUser()
        self.middleware(request)
        self.assertTrue(request.user.is_anonymous)

    def test_missing_bearer_header_leaves_anonymous_user(self):
        request = self.factory.get("/any/endpoint")
        request.user = AnonymousUser()
        self.middleware(request)
        self.assertTrue(request.user.is_anonymous)

    def test_already_authenticated_user_preserved(self):
        request = self.factory.get("/any/endpoint")
        request.user = self.user
        self.middleware(request)
        self.assertEqual(request.user, self.user)

