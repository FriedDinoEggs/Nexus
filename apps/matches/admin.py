from django.contrib import admin

from .models import (
    MatchSet,
    PlayerMatch,
    PlayerMatchParticipant,
    TeamMatch,
)


class PlayerMatchParticipantInline(admin.TabularInline):
    model = PlayerMatchParticipant
    extra = 2
    raw_id_fields = ('player',)


class MatchSetInline(admin.TabularInline):
    model = MatchSet
    extra = 3


@admin.register(PlayerMatch)
class PlayerMatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'team_match', 'number', 'format', 'requirement', 'status', 'winner')
    list_filter = ('status', 'format')
    inlines = [PlayerMatchParticipantInline, MatchSetInline]
    search_fields = ('team_match__team_a__team__name', 'team_match__team_b__team__name')


class PlayerMatchInline(admin.TabularInline):
    model = PlayerMatch
    extra = 0
    show_change_link = True
    fields = ('number', 'format', 'requirement', 'status', 'winner')
    readonly_fields = ('status', 'winner')


@admin.register(TeamMatch)
class TeamMatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'team_a', 'team_b', 'status', 'winner', 'date')
    list_filter = ('status', 'date')
    inlines = [PlayerMatchInline]
    search_fields = ('team_a__team__name', 'team_b__team__name')


admin.site.register(MatchSet)
admin.site.register(PlayerMatchParticipant)
