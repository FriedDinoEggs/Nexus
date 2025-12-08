from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

User = get_user_model()


# Group：[SuperAdmin, EventManager, Member]
# SuperAdmin   : create destroy view change
# EventManager : view change
# Member       : view
class Command(BaseCommand):
    help = 'Create SuperAdmin, EventManager, Member Group and setup permission'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Start create user group and permission !'))

        user_content_type = ContentType.objects.get_for_model(User)
        all_user_permissions = Permission.objects.filter(content_type=user_content_type)

        group_permissions = {
            'SuperAdmin': all_user_permissions,
            'EventManager': all_user_permissions.filter(codename__in=['view_user', 'change_user']),
            'Member': all_user_permissions.filter(codename='view_user'),
        }

        for group_name, permissions in group_permissions.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(f'Create group success: {group_name}')
                group.permissions.set(permissions)
            else:
                self.stdout.write(f'Group already exists: {group_name}')

        self.stdout.write(self.style.SUCCESS('Create Group completed ！'))

        superAdminGroup = Group.objects.get(name='SuperAdmin')
        for u in User.objects.all():
            if u.is_superuser:
                u.groups.add(superAdminGroup)

        # 顯示所有群組及其權限
        for group_name in group_permissions.keys():
            group = Group.objects.get(name=group_name)
            perms = group.permissions.all()
            self.stdout.write(f'\n【{group_name}】')
            if perms.exists():
                for perm in perms:
                    self.stdout.write(f'  - {perm.codename}')
            else:
                self.stdout.write('  (此群組無 User 相關權限)')
