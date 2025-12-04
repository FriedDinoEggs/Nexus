from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserChangeForm, CustomUserCreateForm

# Register your models here.
User = get_user_model()


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreateForm
    form = CustomUserChangeForm

    list_display = ('full_name', 'email', 'date_of_birth', 'created_at', 'updated_at')
    list_filter = ('full_name', 'email', 'date_of_birth')
    search_fields = ('full_name', 'email')
    ordering = ('full_name',)

    fieldsets = (
        (None, {'fields': ('full_name', 'email')}),
        ('Personal Info', {'fields': ('full_name', 'email', 'avatar', 'date_of_birth')}),
        (
            'Permissions',
            {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')},
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'avatar', 'date_of_birth')}),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                ),
            },
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('full_name', 'email', 'password', 'confirm_password'),
            },
        ),
    )
