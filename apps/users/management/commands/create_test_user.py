from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import IntegrityError

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test users'

    def handle(self, *args: Any, **options: Any):
        test_account: dict = {
            'SuperAdmin': {
                'email': 'testAdmin@test.com',
                'password': 'testAdmin',
                'full_name': 'SuperAdmin',
                'group': 'SuperAdmin',
            },
            'EventManager': {
                'email': 'testEventManager@test.com',
                'password': 'testEventManager',
                'full_name': 'EventManager',
                'group': 'EventManager',
            },
            'Member': {
                'email': 'testMember@test.com',
                'password': 'testMember',
                'full_name': 'Member',
                'group': 'Member',
            },
        }

        for role, account_info in test_account.items():
            email = account_info.get('email')
            password = account_info.get('password')
            full_name = account_info.get('full_name')
            group = account_info.get('group')

            # if User.objects.filter(email=email).exists():
            #     self.stdout.write(self.style.WARNING(f'{email} already exists, skipping!!!'))
            #     continue
            try:
                if role == 'SuperAdmin':
                    user = User.objects.create_superuser(
                        email=email,
                        password=password,
                        full_name=full_name,
                    )
                else:
                    user = User.objects.create_user(
                        email=email,
                        password=password,
                        full_name=full_name,
                    )

                user_group = Group.objects.get(name=group)
                user.groups.add(user_group)
            except IntegrityError:
                self.stdout.write(self.style.WARNING(f'{email} already exists, skipping!!!'))
            except Group.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(f'{group} not found! Run: uv run manage.py set_groups')
                )

        self.stdout.write(self.style.SUCCESS('ALL test users and groups are created!!!'))
