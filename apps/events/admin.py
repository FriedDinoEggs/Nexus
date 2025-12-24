from django.contrib import admin

from .models import Event, EventTeam, EventTeamMember, LunchOption, RegistrationLunchOrder


class EventTeamMemberInline(admin.TabularInline):
    model = EventTeamMember
    extra = 1
    autocomplete_fields = ['user']


class EventTeamInline(admin.TabularInline):
    model = EventTeam
    extra = 1
    autocomplete_fields = ['team', 'coach', 'leader']


class LunchOptionInline(admin.TabularInline):
    model = LunchOption
    extra = 1


class RegistrationLunchOrderInline(admin.TabularInline):
    model = RegistrationLunchOrder
    extra = 0
    autocomplete_fields = ['option']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'location', 'start_time', 'end_time', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('name',)
    autocomplete_fields = ['location']
    inlines = [EventTeamInline, LunchOptionInline]


@admin.register(EventTeam)
class EventTeamAdmin(admin.ModelAdmin):
    list_display = ('team', 'event', 'status', 'coach', 'leader', 'created_at')
    list_filter = ('status', 'event', 'created_at')
    search_fields = ('team__name', 'event__name')
    inlines = [EventTeamMemberInline]
    autocomplete_fields = ['event', 'team', 'coach', 'leader']


@admin.register(EventTeamMember)
class EventTeamMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_team', 'is_player', 'is_coach', 'is_staff')
    list_filter = ('is_player', 'is_coach', 'is_staff', 'event_team__event')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'event_team__team__name')
    autocomplete_fields = ['event_team', 'user']
    inlines = [RegistrationLunchOrderInline]


@admin.register(LunchOption)
class LunchOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'event', 'created_at')
    list_filter = ('event', 'price')
    search_fields = ('name', 'event__name')
    autocomplete_fields = ['event']


@admin.register(RegistrationLunchOrder)
class RegistrationLunchOrderAdmin(admin.ModelAdmin):
    list_display = ('member', 'option', 'quantity', 'note', 'created_at')
    list_filter = ('option__event', 'option')
    search_fields = ('member__user__email', 'option__name')
    autocomplete_fields = ['member', 'option']
