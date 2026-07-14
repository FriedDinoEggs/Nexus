from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.relations import PrimaryKeyRelatedField

from apps.core.models import Location

from .models import (
    Event,
    EventMatchTemplate,
    EventMatchTemplateItem,
    EventTeam,
    EventTeamMember,
    LunchOption,
    RegistrationLunchOrder,
)
from .services import EventService


class EventRuleConfigSerializer(serializers.Serializer):
    winning_sets = serializers.IntegerField(
        required=True, help_text='Number of sets to win a PlayerMatch'
    )
    set_winning_points = serializers.IntegerField(
        required=True, help_text='Points needed to win a single set'
    )
    use_deuce = serializers.BooleanField(
        required=True, help_text='Whether to use deuce rule (must win by 2 points)'
    )
    team_winning_points = serializers.IntegerField(
        required=True, help_text='Number of points (matches) to win a TeamMatch'
    )
    play_all_sets = serializers.BooleanField(
        required=True, help_text='Must play all sets, overrides winning_sets setting'
    )
    play_all_matches = serializers.BooleanField(
        required=True, help_text='Must play all matches, overrides team_winning_points setting'
    )
    count_points_by_sets = serializers.BooleanField(
        required=True, help_text='Whether to count set scores (e.g. 4:2) or win/loss (1:0)'
    )


class EventMatchTemplateItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventMatchTemplateItem
        fields = ['id', 'number', 'format', 'requirement']


class EventMatchTemplateSerializer(serializers.ModelSerializer):
    items = EventMatchTemplateItemSerializer(many=True)
    creator_name = serializers.ReadOnlyField(source='creator.full_name')

    class Meta:
        model = EventMatchTemplate
        fields = ['id', 'name', 'creator', 'creator_name', 'items', 'created_at']
        read_only_fields = ['creator', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        request = self.context.get('request')
        creator = request.user if request and request.user.is_authenticated else None

        return EventService.create_match_template(
            name=validated_data['name'], items_data=items_data, creator=creator
        )

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        return EventService.update_match_template(
            template=instance, name=validated_data.get('name'), items_data=items_data
        )


class EventTemplateSerializer(EventRuleConfigSerializer):
    template_items = EventMatchTemplateItemSerializer(
        many=True, required=True, help_text='List of items defining the match structure'
    )


class RegistrationLunchOrderSerializer(serializers.ModelSerializer):
    option_name = serializers.ReadOnlyField(source='option.name')

    class Meta:
        model = RegistrationLunchOrder
        fields = ['id', 'option', 'option_name', 'quantity', 'note']


class EventTeamMemberSerializer(serializers.ModelSerializer):
    user_full_name = serializers.ReadOnlyField(source='user.full_name')
    event_name = serializers.ReadOnlyField(source='event_team.event.name')
    team_name = serializers.ReadOnlyField(source='event_team.team.name')
    lunch_orders = RegistrationLunchOrderSerializer(many=True, required=False)

    class Meta:
        model = EventTeamMember
        fields = [
            'id',
            'status',
            'event_team',
            'user',
            'user_full_name',
            'event_name',
            'team_name',
            'request_waitlist_only',
            'is_player',
            'is_coach',
            'is_staff',
            'lunch_orders',
            'created_at',
        ]
        read_only_fields = ['status', 'user_full_name', 'event_name', 'team_name', 'created_at']

    @transaction.atomic
    def create(self, validated_data):
        lunch_orders_data = validated_data.pop('lunch_orders', [])

        try:
            member = EventService.add_team_member(
                event_team=validated_data['event_team'],
                user=validated_data['user'],
                is_player=validated_data.get('is_player', True),
                is_coach=validated_data.get('is_coach', False),
                is_staff=validated_data.get('is_staff', False),
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(detail=str(e)) from None

        self._process_lunch_data(member, lunch_orders_data)

        return member

    @transaction.atomic()
    def update(self, instance, validated_data):
        lunch_orders_data = validated_data.pop('lunch_orders', [])

        instance.lunch_orders.all().delete()

        self._process_lunch_data(instance, lunch_orders_data)

        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(detail=str(e)) from None

    def _process_lunch_data(self, member, lunch_orders_data):
        if lunch_orders_data:
            orders_payload = [
                {
                    'option_id': order['option'].id,
                    'quantity': order.get('quantity', 1),
                    'note': order.get('note', ''),
                }
                for order in lunch_orders_data
            ]
            try:
                EventService.order_member_lunches(member=member, lunch_orders=orders_payload)
            except DjangoValidationError as e:
                raise serializers.ValidationError(detail=str(e)) from None


class EventTeamSerializer(serializers.ModelSerializer):
    event_name = serializers.ReadOnlyField(source='event.name')
    team_name = serializers.ReadOnlyField(source='team.name')

    class Meta:
        model = EventTeam
        fields = [
            'id',
            'event',
            'event_name',
            'team',
            'team_name',
            'max_member',
            'max_waitlist',
            'status',
            'coach',
            'leader',
        ]

    def create(self, validated_data):
        try:
            return EventService.register_team(
                event=validated_data['event'],
                team=validated_data['team'],
                status=validated_data.get('status', EventTeam.StatusChoices.APPROVED),
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(detail=str(e)) from None

    def validate(self, data):
        if self.instance:
            member_nums = self.instance.event_team_members.filter(status='RG').count()
            waitlist_nums = self.instance.event_team_members.filter(status='WL').count()
            if (max_member := data.get('max_member')) is not None and member_nums > max_member:
                raise serializers.ValidationError(
                    {'max_number': f'{member_nums} members have registerd so far.'}
                )
            if (
                max_waitlist := data.get('max_waitlist')
            ) is not None and waitlist_nums > max_waitlist:
                raise serializers.ValidationError(
                    {'max_waitlist': f'{waitlist_nums} members have registerd so far.'}
                )
        return super().validate(data)


class LunchOptionSerializer(serializers.ModelSerializer):
    event = PrimaryKeyRelatedField(queryset=Event.objects.all(), required=False)

    class Meta:
        model = LunchOption
        fields = ['id', 'event', 'name', 'price']


class EventSerializer(serializers.ModelSerializer):
    event_teams = EventTeamSerializer(many=True, read_only=True)
    lunch_options = LunchOptionSerializer(many=True, required=False)
    rule_config = EventRuleConfigSerializer(required=True, write_only=True)
    location_name = serializers.CharField(required=False, allow_null=True, max_length=128)
    match_template = serializers.PrimaryKeyRelatedField(
        queryset=EventMatchTemplate.objects.all(), required=True, write_only=True
    )

    class Meta:
        model = Event
        fields = [
            'id',
            'name',
            'start_time',
            'end_time',
            'all_day',
            'type',
            'location_name',
            'event_teams',
            'lunch_options',
            'rule_config',
            'match_template',
            'match_template',
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.location:
            ret['location_name'] = instance.location.name

        match_config = getattr(instance, 'match_config', None)
        ret['rule_config'] = match_config.rule_config if match_config else None

        return ret

    @transaction.atomic
    def create(self, validated_data):
        lunch_options_data = validated_data.pop('lunch_options', [])
        rule_config_data = validated_data.pop('rule_config', None)
        location_name = validated_data.pop('location_name', None)
        match_template = validated_data.pop('match_template', None)

        if location_name:
            location, _ = Location.objects.get_or_create(name=location_name)
            validated_data['location'] = location

        try:
            event = EventService.create_event(
                name=validated_data['name'],
                event_type=validated_data.get('type', Event.TypeChoices.LEAGUE),
                start_time=validated_data.get('start_time'),
                end_time=validated_data.get('end_time'),
                location=validated_data.get('location'),
            )

            if lunch_options_data:
                options = [
                    LunchOption(event=event, name=item.get('name'), price=item.get('price', 80))
                    for item in lunch_options_data
                ]
                LunchOption.objects.bulk_create(options)

            if rule_config_data:
                self._apply_event_config(event, rule_config_data, match_template)
                # event.match_config.refresh_from_db()

            return event
        except DjangoValidationError as e:
            raise serializers.ValidationError(detail=str(e)) from None

    @transaction.atomic
    def update(self, instance, validated_data):
        lunch_options_data = validated_data.pop('lunch_options', None)
        rule_config_data = validated_data.pop('rule_config', None)
        location_name = validated_data.pop('location_name', None)
        match_template = validated_data.pop('match_template', None)

        if location_name is not None:
            if location_name:
                location, _ = Location.objects.get_or_create(name=location_name)
                validated_data['location'] = location
            else:
                validated_data['location'] = None

        instance = super().update(instance, validated_data)

        if lunch_options_data is not None:
            instance.lunch_options.all().delete()
            options = [
                LunchOption(event=instance, name=item.get('name'), price=item.get('price', 80))
                for item in lunch_options_data
            ]
            LunchOption.objects.bulk_create(options)

        if rule_config_data:
            self._apply_event_config(instance, rule_config_data, match_template)

        return instance

    def _apply_event_config(self, event, config_data, match_template_id=None):
        rule_settings = dict(config_data)

        EventService.set_event_config(
            event=event, template=match_template_id, rule_config=rule_settings
        )


class EventCalendarSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField(source='name')
    start = serializers.DateTimeField(source='start_time')
    end = serializers.DateTimeField(source='end_time')
    allDay = serializers.BooleanField(source='all_day')
