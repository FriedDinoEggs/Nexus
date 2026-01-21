import secrets
from dataclasses import asdict

from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)

from apps.users.models import ScocialAccount
from apps.users.services import UserVerificationServices
from apps.users.services.social_services import SocialServices

User = get_user_model()


class UserEmailVerificationSerializer(serializers.Serializer):
    token = serializers.UUIDField()


class UserEmailVerificationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password_confirm = serializers.CharField(write_only=True)

    MIN_AGE = 5
    MAX_AGE = 120

    class Meta:
        model = User
        fields = [
            'email',
            'password',
            'password_confirm',
            'full_name',
            'date_of_birth',
            'avatar',
            'is_active',
        ]

        extra_kwargs = {
            'password': {
                'write_only': True,
            },
            'password_confirm': {
                'write_only': True,
            },
            'date_of_birth': {
                'required': False,
            },
            'full_name': {
                'required': False,
                'default': '',
            },
        }

    def get_fields(self):
        fields = super().get_fields()
        user = self.context['request'].user
        if not hasattr(user, '_cached_group_names'):
            user._cached_group_names = {g.name for g in user.groups.all()}

        if 'SuperAdmin' not in user._cached_group_names:
            fields.pop('is_active')

        return fields

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return attrs

    def validate_date_of_birth(self, attrs):
        from datetime import date

        today = date.today()
        age = today.year - attrs.year - ((today.month, today.day) < (attrs.month, attrs.day))
        if age < self.MIN_AGE or age > self.MAX_AGE:
            raise serializers.ValidationError(
                f'Invalid age. Must be between {self.MIN_AGE} and {self.MAX_AGE}.'
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        full_name = validated_data.pop('full_name')

        user = User.objects.create_user(
            email=email, password=password, full_name=full_name, **validated_data
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'password',
            'full_name',
            'date_of_birth',
            'avatar',
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'min_length': 8},
            'full_name': {'default': ''},
        }

    def create(self, validated_data):
        email = validated_data.pop('email')
        password = validated_data.pop('password')

        allowed_fields = ['full_name', 'date_of_birth', 'avatar', 'is_active']
        user_data = {k: v for k, v in validated_data.items() if k in allowed_fields}
        user = User.objects.create_user(email=email, password=password, **user_data)
        return user

    def update(self, instance, validated_data):
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
        instance.email = validated_data.get('email', instance.email)
        instance.full_name = validated_data.get('full_name', instance.full_name)
        instance.date_of_birth = validated_data.get('date_of_birth', instance.date_of_birth)
        instance.avatar = validated_data.get('avatar', instance.avatar)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['is_active'] = instance.is_active
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        allow_fields = {'id', 'full_name', 'avatar'}

        # cache所有group name
        if not hasattr(user, '_cached_group_names'):
            user._cached_group_names = {g.name for g in user.groups.all()}
        user_group = user._cached_group_names

        if 'SuperAdmin' in user_group:
            return data
        if 'EventManager' in user_group:
            allow_fields.update(['email'])
        if user.pk == instance.pk:
            allow_fields.update(['email', 'date_of_birth'])

        return {k: v for k, v in data.items() if k in allow_fields}


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'), email=email, password=password)
            if not user:
                raise AuthenticationFailed('Invalid credentials')
            if not user.is_active:
                raise AuthenticationFailed('Account has been disabled')
            return user
        else:
            raise serializers.ValidationError('請提供帳號密碼')


class UserVerificationRequestSerializer(serializers.Serializer):
    MODE_CHOICE = [
        ('verifyEmail', 'verify email'),
        ('resetPassword', 'reset password'),
    ]
    mode = serializers.ChoiceField(choices=MODE_CHOICE, required=True)


class UserVerificationVerifySerilizer(serializers.Serializer):
    MODE_CHOICE = [
        ('verifyEmail', 'verify email'),
        ('resetPassword', 'reset password'),
    ]
    mode = serializers.ChoiceField(choices=MODE_CHOICE, required=True)
    code = serializers.CharField(required=True)


class UserPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class UserPasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    verification_code = serializers.CharField()

    def validate(self, attrs):
        if not UserVerificationServices.verify_reset_pwd(
            code=attrs['verification_code'], account=attrs['email']
        ):
            raise serializers.ValidationError('verification error')
        return attrs


class MyToeknRefreshSerializer(TokenRefreshSerializer):
    from typing import Any

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        data = super().validate(attrs)
        data['access_token'] = data['access']
        data['refresh_token'] = data['refresh']

        return data


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    from typing import Any

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        data = super().validate(attrs)
        data['access_token'] = data['access']
        data['refresh_token'] = data['refresh']

        return data


class GoogleLoginSerializer(serializers.Serializer):
    code = serializers.CharField(write_only=True)

    def validate(self, attrs):
        info = SocialServices.get_social_info('google', attrs['code'])

        if not info:
            raise serializers.ValidationError({'code': 'Invalid authorization code'})

        return {'oauth_info': asdict(info)}

    def create(self, validated_data):
        info = validated_data['oauth_info']

        user = User.objects.filter(email=info['email']).first()
        if not user:
            password = secrets.token_urlsafe(12)
            user = User.objects.create_user(
                email=info['email'],
                password=password,
                full_name=info.get('full_name', ''),
                is_active=True,
                is_verified=True,
            )

        social_account, created = ScocialAccount.objects.get_or_create(
            social_id=info['provider_user_id'],
            social_type=info['provider'],
            defaults={
                'user': user,
            },
        )

        if not created:
            social_account.save(update_fields=['last_login'])

        return user
