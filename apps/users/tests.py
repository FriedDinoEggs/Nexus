from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import AccessToken

from apps.users.models import BlackListToken
from apps.users.serializers import UserProfileSerializer, UserRegistrationSerializer
from apps.users.services import BlackListService, UserVerificationServices

User = get_user_model()


class BaseUsersTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.superadmin_group, _ = Group.objects.get_or_create(name='SuperAdmin')
        self.manager_group, _ = Group.objects.get_or_create(name='EventManager')
        self.member_group, _ = Group.objects.get_or_create(name='Member')

    def make_user(self, *, email, password='password123', full_name='User', groups=None, **extra):
        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            **extra,
        )
        if groups is not None:
            user.groups.set(groups)
        return user

    def make_request(self, user):
        request = self.factory.get('/api/v1/users/')
        request.user = user
        return request


class UserRegistrationSerializerTests(BaseUsersTestCase):
    def test_superadmin_can_see_is_active_field(self):
        user = self.make_user(
            email='admin@test.com',
            full_name='Admin',
            groups=[self.superadmin_group],
        )
        serializer = UserRegistrationSerializer(context={'request': self.make_request(user)})

        self.assertIn('is_active', serializer.fields)

    def test_non_superadmin_cannot_see_is_active_field(self):
        user = self.make_user(
            email='member@test.com',
            full_name='Member',
            groups=[self.member_group],
        )
        serializer = UserRegistrationSerializer(context={'request': self.make_request(user)})

        self.assertNotIn('is_active', serializer.fields)

    def test_validate_rejects_password_mismatch(self):
        user = self.make_user(
            email='member@test.com',
            full_name='Member',
            groups=[self.member_group],
        )
        serializer = UserRegistrationSerializer(
            data={
                'email': 'new@test.com',
                'password': 'StrongPass123!@#',
                'password_confirm': 'StrongPass123!@4',
            },
            context={'request': self.make_request(user)},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('password_confirm', serializer.errors)

    def test_validate_date_of_birth_rejects_out_of_range_age(self):
        user = self.make_user(
            email='member@test.com',
            full_name='Member',
            groups=[self.member_group],
        )
        serializer = UserRegistrationSerializer(context={'request': self.make_request(user)})

        with self.assertRaises(ValidationError):
            serializer.validate_date_of_birth(date.today().replace(year=date.today().year - 3))

        with self.assertRaises(ValidationError):
            serializer.validate_date_of_birth(date(1900, 1, 1))


class UserProfileSerializerTests(BaseUsersTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.make_user(
            email='admin@test.com',
            full_name='Admin',
            groups=[self.superadmin_group],
        )
        self.manager = self.make_user(
            email='manager@test.com',
            full_name='Manager',
            groups=[self.manager_group],
        )
        self.member = self.make_user(
            email='member@test.com',
            full_name='Member',
            groups=[self.member_group],
            date_of_birth=date(2000, 1, 1),
        )

    def test_superadmin_sees_full_user_profile_fields(self):
        serializer = UserProfileSerializer(
            self.member,
            context={'request': self.make_request(self.admin)},
        )

        self.assertEqual(
            set(serializer.data.keys()),
            {'id', 'email', 'full_name', 'date_of_birth', 'avatar', 'is_active'},
        )

    def test_manager_sees_other_user_email_but_not_date_of_birth(self):
        serializer = UserProfileSerializer(
            self.member,
            context={'request': self.make_request(self.manager)},
        )

        self.assertIn('email', serializer.data)
        self.assertNotIn('date_of_birth', serializer.data)
        self.assertNotIn('is_active', serializer.data)

    def test_member_cannot_see_other_user_email(self):
        other_member = self.make_user(
            email='other@test.com',
            full_name='Other Member',
            groups=[self.member_group],
        )
        serializer = UserProfileSerializer(
            other_member,
            context={'request': self.make_request(self.member)},
        )

        self.assertEqual(set(serializer.data.keys()), {'id', 'full_name', 'avatar'})

    def test_owner_sees_private_fields_on_own_profile(self):
        serializer = UserProfileSerializer(
            self.member,
            context={'request': self.make_request(self.member)},
        )

        self.assertIn('email', serializer.data)
        self.assertIn('date_of_birth', serializer.data)
        self.assertNotIn('is_active', serializer.data)


class UserVerificationServicesTests(BaseUsersTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = self.make_user(
            email='verify@test.com',
            full_name='Verify User',
            groups=[self.member_group],
            is_verified=False,
        )

    @patch('apps.users.services.services.send_unified_mail_task.delay')
    @patch('apps.users.services.services.uuid6.uuid7')
    def test_send_verification_mail_stores_cache_and_sends_mail(self, mock_uuid7, mock_delay):
        mock_uuid7.return_value = SimpleNamespace(hex='verifytoken')

        UserVerificationServices.send_verification_mail(
            user=self.user,
            base_url='http://127.0.0.1:8000/',
        )

        self.assertEqual(
            cache.get(f'{UserVerificationServices.cache_verify_header}verifytoken'),
            self.user.id,
        )
        mock_delay.assert_called_once_with(
            mail_type='verify',
            verification_url='http://127.0.0.1:8000/api/v1/verification/verify/?mode=verifyEmail&code=verifytoken',
            to=self.user.email,
        )

    @patch('apps.users.services.services.send_unified_mail_task.delay')
    def test_verify_mail_marks_user_verified_and_consumes_token(self, mock_delay):
        cache.set(
            f'{UserVerificationServices.cache_verify_header}verifytoken', self.user.id, timeout=60
        )

        result = UserVerificationServices.verify_mail(token='verifytoken')

        self.user.refresh_from_db()
        self.assertEqual(result, 1)
        self.assertTrue(self.user.is_verified)
        self.assertIsNone(cache.get(f'{UserVerificationServices.cache_verify_header}verifytoken'))
        mock_delay.assert_called_once_with(mail_type='welcome', to=self.user.email)

    @patch('apps.users.services.services.send_unified_mail_task.delay')
    @patch('apps.users.services.services.random.randint', return_value=123456)
    def test_send_reset_pwd_mail_stores_code_and_sends_mail(self, mock_randint, mock_delay):
        UserVerificationServices.send_reset_pwd_mail(account=self.user.email)

        self.assertEqual(
            cache.get(self.user.email),
            f'{UserVerificationServices.cache_reset_pwd_header}123456',
        )
        mock_randint.assert_called_once()
        mock_delay.assert_called_once_with(
            mail_type='reset_pwd',
            code='123456',
            to=self.user.email,
        )

    def test_verify_reset_pwd_returns_true_once_then_consumes_code(self):
        cache.set(
            self.user.email,
            f'{UserVerificationServices.cache_reset_pwd_header}654321',
            timeout=60,
        )

        self.assertTrue(
            UserVerificationServices.verify_reset_pwd(
                code='654321',
                account=self.user.email,
            )
        )
        self.assertFalse(
            UserVerificationServices.verify_reset_pwd(
                code='654321',
                account=self.user.email,
            )
        )


class BlackListServiceTests(BaseUsersTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = self.make_user(
            email='blacklist@test.com',
            full_name='Blacklist User',
            groups=[self.member_group],
        )

    def test_set_blacklisted_access_token_persists_record(self):
        token = AccessToken.for_user(self.user)

        BlackListService.set_blacklisted(user=self.user, token=token)

        black_name = f'{BlackListService.blacklist_prefix}:{token["jti"]}'
        self.assertTrue(BlackListToken.objects.filter(token=black_name, user=self.user).exists())
        self.assertTrue(BlackListService.is_token_blacklisted(token))

    @patch('apps.users.services.services.cache.get', side_effect=RuntimeError('cache down'))
    def test_is_token_blacklisted_falls_back_to_db(self, _mock_cache_get):
        token = AccessToken.for_user(self.user)
        black_name = f'{BlackListService.blacklist_prefix}:{token["jti"]}'
        BlackListToken.objects.create(
            token=black_name,
            expires_at=timezone.now(),
            user=self.user,
        )

        self.assertTrue(BlackListService.is_token_blacklisted(token))

    def test_is_token_blacklisted_returns_false_without_token(self):
        self.assertFalse(BlackListService.is_token_blacklisted(None))
