import uuid

from django.contrib import auth
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group
from django.db import models
from django.utils import timezone

# Create your models here.


def user_directory_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    # file will be uploaded to MEDIA_ROOT/user_<pk>/<filename>
    if instance.pk is None:
        return f'user_new/{filename}'
    return f'user_{instance.pk}/{filename}'


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    # https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#writing-a-manager-for-a-custom-user-model
    def create_user(self, email: str, full_name: str, password: str = None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address!')
        # if not full_name or len(full_name.strip()) < 2:
        #     raise ValueError('Full name must be at lest 2 caraters long!!!')

        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name.strip(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        default_group, _ = Group.objects.get_or_create(name='Member')
        user.groups.add(default_group)
        return user

    def create_superuser(self, email: str, full_name: str, password: str = None, **extra_fields):  # type: ignore
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        user = self.create_user(email=email, full_name=full_name, password=password, **extra_fields)
        user.save(using=self._db)
        return user

    # 這邊抄 django 的！！！
    def with_perm(self, perm, is_active=True, include_superusers=True, backend=None, obj=None):
        if backend is None:
            backends = auth._get_backends(return_tuples=True)
            if len(backends) == 1:
                backend, _ = backends[0]
            else:
                raise ValueError(
                    'You have multiple authentication backends configured and '
                    'therefore must provide the `backend` argument.'
                )
        elif not isinstance(backend, str):
            raise TypeError('backend must be a dotted import path string (got %r).' % backend)
        else:
            backend = auth.load_backend(backend)
        if hasattr(backend, 'with_perm'):
            return backend.with_perm(
                perm,
                is_active=is_active,
                include_superusers=include_superusers,
                obj=obj,
            )
        return self.none()


class User(AbstractUser):
    # TODO: 一些欄位尚未實做，新增功能時要檢查！！
    # TODO: has_perm
    username = None
    first_name = None
    last_name = None
    email = models.EmailField(unique=True, max_length=254)
    full_name = models.CharField(blank=True, default='', max_length=150)
    date_of_birth = models.DateField(null=True, blank=True)
    avatar = models.ImageField(null=True, blank=True, upload_to=user_directory_path)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # avatar
    # phone
    # is_verified

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    objects = CustomUserManager()

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.full_name

    def clean(self):
        super().clean()

    def __str__(self):
        return self.email

    class Meta:
        ordering = ['id']

        indexes = [
            models.Index(
                fields=[
                    'full_name',
                ],
                name='core_user_full_name_index',
            ),
        ]


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        count = self.update(deleted_at=timezone.now())
        return (count, {self.model._meta.label: count})

    def restore(self):
        count = self.update(deleted_at=None)
        return (count, {self.model._meta.label: count})

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class SoftDeleteModel(TimeStampedModel):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    all_objects = SoftDeleteQuerySet.as_manager()
    objects = SoftDeleteManager()

    class Meta:
        abstract = True
        default_manager_name = 'objects'

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(using=using)
        return (1, {self._meta.label: 1})

    def restore(self):
        self.deleted_at = None
        self.save()
        return (1, {self._meta.label: 1})
