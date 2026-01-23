from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    MatchTemplate,
    MatchTemplateItem,
    PlayerMatch,
    PlayerMatchParticipant,
    TeamMatch,
)
from .services import MatchService

User = get_user_model()


class MatchTemplateItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchTemplateItem
        fields = ['id', 'number', 'format', 'requirement']


class MatchTemplateSerializer(serializers.ModelSerializer):
    items = MatchTemplateItemSerializer(many=True)
    creator_name = serializers.ReadOnlyField(source='creator.full_name')

    class Meta:
        model = MatchTemplate
        fields = ['id', 'name', 'creator', 'creator_name', 'items', 'created_at']
        read_only_fields = ['creator', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        request = self.context.get('request')
        creator = request.user if request and request.user.is_authenticated else None

        return MatchService.create_match_template(
            name=validated_data['name'], items_data=items_data, creator=creator
        )

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        return MatchService.update_match_template(
            template=instance, name=validated_data.get('name'), items_data=items_data
        )


class PlayerMatchParticipantSerializer(serializers.ModelSerializer):
    player_name = serializers.ReadOnlyField(source='player.full_name')

    class Meta:
        model = PlayerMatchParticipant
        fields = ['id', 'player', 'player_name', 'player_name_backup', 'side', 'position']
        extra_kwargs = {
            'player': {'required': False},
            'side': {'required': False},
        }


class PlayerMatchSerializer(serializers.ModelSerializer):
    participants = PlayerMatchParticipantSerializer(many=True, required=False)

    class Meta:
        model = PlayerMatch
        fields = [
            'id',
            'team_match',
            'number',
            'date',
            'time',
            'status',
            'winner',
            'format',
            'requirement',
            'participants',
        ]
        read_only_fields = ['team_match', 'format', 'status', 'winner']


class TeamMatchSerializer(serializers.ModelSerializer):
    player_matches = serializers.JSONField(write_only=True, required=False)
    # player_matches_display is used for read output to avoid confusion with the input JSONField
    matches_info = PlayerMatchSerializer(source='player_matches', many=True, read_only=True)
    team_a_name = serializers.ReadOnlyField(source='team_a.team.name')
    team_b_name = serializers.ReadOnlyField(source='team_b.team.name')

    class Meta:
        model = TeamMatch
        fields = [
            'id',
            'team_a',
            'team_a_name',
            'team_b',
            'team_b_name',
            'number',
            'date',
            'time',
            'status',
            'winner',
            'player_matches',
            'matches_info',
        ]
        extra_kwargs = {
            'team_a': {
                'required': True,
            },
            'team_b': {
                'required': True,
            },
        }

    def create(self, validated_data):
        # player_matches_data should look like:
        # [
        #   {"number": 1, "side_a": [{"player": id, "position": 1}], "side_b": [...]}
        # ]
        # We need to transform it for the service
        raw_player_matches = validated_data.pop('player_matches', [])
        transformed_data = []

        for pm_item in raw_player_matches:
            participants = []
            # Map side_a to side A
            for p in pm_item.get('side_a', []):
                p['side'] = 'A'
                participants.append(p)
            # Map side_b to side B
            for p in pm_item.get('side_b', []):
                p['side'] = 'B'
                participants.append(p)

            transformed_data.append({'number': pm_item.get('number'), 'participants': participants})

        try:
            return MatchService.create_team_match_full(
                team_a=validated_data['team_a'],
                team_b=validated_data['team_b'],
                match_number=validated_data['number'],
                player_matches_data=transformed_data,
            )
        except (ValueError, DjangoValidationError) as e:
            raise serializers.ValidationError(detail=str(e)) from None
