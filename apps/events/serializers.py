from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.relations import PrimaryKeyRelatedField

from apps.core.models import Location

from .models import (
    Event,
    EventMatchConfiguration,
    EventMatchTemplate,
    EventMatchTemplateItem,
    EventTeam,
    EventTeamMember,
    LunchOption,
    RegistrationLunchOrder,
)
from .services import EventService


class EventMatchConfigurationSerializer(serializers.ModelSerializer):
    template = serializers.PrimaryKeyRelatedField(queryset=EventMatchTemplate.objects.all())
    template_name = serializers.ReadOnlyField(source='template.name')

    class Meta:
        model = EventMatchConfiguration
        fields = ['id', 'template', 'template_name', 'rule_config']


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
            'event_team',
            'user',
            'user_full_name',
            'event_name',
            'team_name',
            'is_player',
            'is_coach',
            'is_staff',
            'lunch_orders',
            'created_at',
        ]
        read_only_fields = ['user_full_name', 'event_name', 'team_name', 'created_at']

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

        return super().update(instance, validated_data)

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
        fields = ['id', 'event', 'event_name', 'team', 'team_name', 'status', 'coach', 'leader']

    def create(self, validated_data):
        try:
            return EventService.register_team(
                event=validated_data['event'],
                team=validated_data['team'],
                status=validated_data.get('status', EventTeam.StatusChoices.APPROVED),
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(detail=str(e)) from None


class LunchOptionSerializer(serializers.ModelSerializer):
    event = PrimaryKeyRelatedField(queryset=Event.objects.all(), required=False)

    class Meta:
        model = LunchOption
        fields = ['id', 'event', 'name', 'price']


class EventLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'address']


class EventSerializer(serializers.ModelSerializer):
    event_teams = EventTeamSerializer(many=True, read_only=True)
    lunch_options = LunchOptionSerializer(many=True, required=False)
    match_config = EventMatchConfigurationSerializer(required=False)
    location = EventLocationSerializer(required=False)
    location_name = serializers.ReadOnlyField(source='location.name')

    class Meta:
        model = Event
        fields = [
            'id',
            'name',
            'start_time',
            'end_time',
            'type',
            'location',
            'location_name',
            'event_teams',
            'lunch_options',
            'match_config',
        ]

    @transaction.atomic
    def create(self, validated_data):
        lunch_options_data = validated_data.pop('lunch_options', [])
        match_config_data = validated_data.pop('match_config', None)

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

            if match_config_data:
                EventService.set_event_config(
                    event=event,
                    template=match_config_data['template'],
                    rule_config=match_config_data.get('rule_config'),
                )

            return event
        except DjangoValidationError as e:
            raise serializers.ValidationError(detail=str(e)) from None

    @transaction.atomic
    def update(self, instance, validated_data):
        lunch_options_data = validated_data.pop('lunch_options', None)
        match_config_data = validated_data.pop('match_config', None)

        instance = super().update(instance, validated_data)

        if lunch_options_data is not None:
            instance.lunch_options.all().delete()
            options = [
                LunchOption(event=instance, name=item.get('name'), price=item.get('price', 80))
                for item in lunch_options_data
            ]
            LunchOption.objects.bulk_create(options)

        if match_config_data:
            EventService.set_event_config(
                event=instance,
                template=match_config_data['template'],
                rule_config=match_config_data.get('rule_config'),
            )

        return instance


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
