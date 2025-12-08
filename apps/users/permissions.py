from django.contrib.auth import get_user_model
from rest_framework import permissions

User = get_user_model()


class IsSuperAdminGroup(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.groups.filter(name='SuperAdmin').exists()


class IsEventManagerGroup(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.groups.filter(name='EventManager').exists()


class IsMemberGroup(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.groups.filter(name='Member').exists()


class IsOwnerObject(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user == obj
