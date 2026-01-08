from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.fields import ValidationError

from apps.teams.models import Team
from apps.teams.services import TeamService


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name', 'leader', 'coach', 'members']

        read_only_fields = [
            'members',
        ]

    def create(self, validated_data):
        """
        Create a Team instance using validated serializer data and the provided user.
        
        Parameters:
            validated_data (dict): Serializer-validated data; must include a 'user' key and other Team fields.
        
        Returns:
            team: The created Team instance.
        
        Raises:
            serializers.ValidationError: If model-level validation fails during creation (maps underlying DjangoValidationError).
        """
        user = validated_data.pop('user')
        try:
            team = TeamService.create_team(user=user, **validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(detail=str(e)) from None

        return team

    @transaction.atomic()
    def update(self, instance, validated_data):
        """
        Update a Team instance with the provided validated data, transferring leadership if the leader changes.
        
        Parameters:
            instance (Team): The Team model instance to update.
            validated_data (dict): A mapping of validated fields to update; may include a 'leader' key to transfer leadership.
        
        Returns:
            Team: The updated Team instance.
        
        Raises:
            rest_framework.fields.ValidationError: If underlying model validation fails (original DjangoValidationError is converted).
        """
        new_leader = validated_data.pop('leader', None)

        try:
            if new_leader and instance.leader != new_leader:
                TeamService.transfer_leadership(instance, new_leader)
            team = TeamService.update_team(instance, **validated_data)
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e)) from None
        return team