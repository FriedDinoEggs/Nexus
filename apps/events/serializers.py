from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.relations import PrimaryKeyRelatedField

from .models import Event, EventTeam, EventTeamMember, LunchOption, RegistrationLunchOrder
from .services import EventService


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

        return member


class EventTeamSerializer(serializers.ModelSerializer):
    event_name = serializers.ReadOnlyField(source='event.name')
    team_name = serializers.ReadOnlyField(source='team.name')

    # parent_lookup_kwargs = {
    #     'event_pk': 'event__pk',
    # }

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


class EventSerializer(serializers.ModelSerializer):
    event_teams = EventTeamSerializer(many=True, read_only=True)
    lunch_options = LunchOptionSerializer(many=True, required=False)
    # location_name = serializers.ReadOnlyField(source='location.name')

    class Meta:
        model = Event
        fields = [
            'id',
            'name',
            'start_time',
            'end_time',
            'type',
            'location',
            # 'location_name',
            'event_teams',
            'lunch_options',
        ]
        depth = 1

    @transaction.atomic
    def create(self, validated_data):
        lunch_options_data = validated_data.pop('lunch_options', [])

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

            return event
        except DjangoValidationError as e:
            raise serializers.ValidationError(detail=str(e)) from None

    @transaction.atomic
    def update(self, instance, validated_data):
        lunch_options_data = validated_data.pop('lunch_options', None)

        instance = super().update(instance, validated_data)

        if lunch_options_data is not None:
            instance.lunch_options.all().delete()
            options = [
                LunchOption(event=instance, name=item.get('name'), price=item.get('price', 80))
                for item in lunch_options_data
            ]
            LunchOption.objects.bulk_create(options)

        return instance
