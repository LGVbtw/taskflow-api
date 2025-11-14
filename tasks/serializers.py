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
        model = Task
        fields = ('id', 'title', 'status', 'created_at', 'owner', 'description')


class MessageSerializer(serializers.ModelSerializer):
    """Sérialiseur pour afficher les messages liés à une Task ou Need."""
    author = serializers.ReadOnlyField(source='author.username')

    class Meta:
        model = __import__('tasks.models', fromlist=['Message']).Message
        fields = ('id', 'content', 'created_at', 'author', 'parent')


class MessageCreateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour créer un message. Permet d'indiquer task ou need via context."""
    class Meta:
        model = __import__('tasks.models', fromlist=['Message']).Message
        fields = ('id', 'content', 'parent')

    class Meta:
        model = Need
        fields = ('id', 'title', 'description', 'created_at', 'owner', 'converted', 'converted_at', 'converted_by')

    class Meta:
        model = Need
        fields = ('id', 'title', 'description', 'created_at', 'owner', 'converted', 'converted_at', 'converted_by')
        read_only_fields = ('converted', 'converted_at', 'converted_by')


# ===== MERGED FROM tasks/api/serializers.py =====
# The following classes were appended from tasks/api/serializers.py
# during an automatic consolidation. Any conflicting class names were
# renamed with a `_api` suffix. See `.backups/tasks_api_serializers.py` for
# the original file.

from tasks.models import Task as _Task_api, Need as _Need_api, Message as _Message_api
from rest_framework import serializers as _serializers_api


class TaskSerializer_api(_serializers_api.ModelSerializer):
    owner = _serializers_api.ReadOnlyField(source='owner.username')

    class Meta:
        model = _Task_api
        fields = ('id', 'title', 'status', 'created_at', 'owner')


class NeedSerializer_api(_serializers_api.ModelSerializer):
    owner = _serializers_api.ReadOnlyField(source='owner.username')

    class Meta:
        model = _Need_api
        fields = ('id', 'title', 'description', 'created_at', 'owner', 'converted', 'converted_at', 'converted_by')


class MessageSerializer_api(_serializers_api.ModelSerializer):
    author = _serializers_api.ReadOnlyField(source='author.username')

    class Meta:
        model = _Message_api
        fields = ('id', 'content', 'created_at', 'author', 'parent', 'task', 'need')


class MessageCreateSerializer_api(_serializers_api.ModelSerializer):
    class Meta:
        model = _Message_api
        fields = ('id', 'content', 'parent', 'task', 'need')