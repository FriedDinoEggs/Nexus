from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password_confirm = serializers.CharField(write_only=True)

    MIN_AGE = 5
    MAX_AGE = 120

    class Meta:
        model = User
        fields = ['email', 'password', 'password_confirm', 'full_name', 'date_of_birth', 'avatar']

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

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return attrs

    def validate_date_of_birth(self, attrs):
        from datetime import date

        today = date.today()
        age = today.year - attrs.year - ((today.month, today.day) < (attrs.month, attrs.day))
        if age < self.MIN_AGE or self.MAX_AGE > 120:
            raise serializers.ValidationError(
                'Invalid age. Must be between {self.MIN_AGE} and {self.MAX_AGE}.'
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data['full_name'],
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
        }

    def create(self, validated_data):
        email = validated_data.pop('email')
        password = validated_data.pop('password')

        allowed_fields = ['full_name', 'date_of_birth', 'avatar']
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
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        # view = self.context.get('view')
        # action = getattr(view, 'action', None) if view else None

        if not user or not user.is_authenticated:
            return {'id': data.get('id'), 'full_name': data.get('full_name')}

        allow_fields = {'id', 'full_name', 'avatar'}

        # cache所有group name
        if not hasattr(user, '_cached_group_names'):
            user._cached_group_names = {g.name for g in user.groups.all()}
        user_group = user._cached_group_names

        if 'SuperAdmin' in user_group:
            return data
        if 'EventManager' in user_group or user.pk == instance.pk:
            allow_fields.update(['email'])

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
