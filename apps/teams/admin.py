from django.contrib import admin

from .models import Team, TeamMember

# Register your models here.


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 1
    autocomplete_fields = ['team', 'user']


@admin.register(Team)
class CustomTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'leader', 'coach')
    inlines = [TeamMemberInline]
    list_filter = ('leader', 'members')
    search_fields = (
        'name',
        'leader__full_name',
        'leader__email',
        'coach__full_name',
        'coach__email',
        'creator__full_name',
        'creator__email',
    )
    ordering = ('created_at',)
