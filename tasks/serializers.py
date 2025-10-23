"""
Sérialiseurs pour l'application des tâches.

Ce module expose les sérialiseurs utilisés par l'API pour convertir les
instances du modèle Task vers/depuis des représentations JSON.
"""

from rest_framework import serializers
from .models import Task
from .models import Need


class TaskSerializer(serializers.ModelSerializer):
    """Sérialiseur pour le modèle Task.

    Représentation (champs) :
        - id : clé primaire entière (auto-générée par Django).
        - title : titre de la tâche (chaîne).
        - status : statut (une des valeurs "A faire", "En cours", "Fait").
        - created_at : date/heure ISO de création.
        - owner : nom d'utilisateur du propriétaire (read-only) ou null.

    Remarques :
        - Le champ `owner` est en lecture seule et provient de `owner.username`.
        - La validation du champ `status` est effectuée par le modèle Task.
    """
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Task
        fields = "__all__"


class NeedSerializer(serializers.ModelSerializer):
    """Sérialiseur pour le modèle Need.

    Le champ `owner` est en lecture seule et affiche le nom d'utilisateur.
    """
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Need
        fields = ('id', 'title', 'description', 'created_at', 'owner', 'converted', 'converted_at', 'converted_by')
        read_only_fields = ('converted', 'converted_at', 'converted_by')