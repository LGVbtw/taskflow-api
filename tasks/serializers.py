"""
Sérialiseurs pour l'application des tâches.

Ce module expose les sérialiseurs utilisés par l'API pour convertir les
instances du modèle Task vers/depuis des représentations JSON.
"""

from rest_framework import serializers
from .models import Task, TaskType
from .models import Need


class TaskSerializer(serializers.ModelSerializer):
    """Expose les tâches en incluant leur type fonctionnel et le parent éventuel."""

    owner = serializers.ReadOnlyField(source="owner.username")
    task_type_code = serializers.SlugRelatedField(
        source="task_type",
        slug_field="code",
        queryset=TaskType.objects.all(),
        required=False,
        allow_null=True,
    )
    task_type_label = serializers.CharField(source="task_type.label", read_only=True)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "status",
            "created_at",
            "owner",
            "task_type_code",
            "task_type_label",
            "parent",
        )
        read_only_fields = ("created_at", "owner", "task_type_label")

    def validate_parent(self, value):
        instance = getattr(self, "instance", None)
        if value and instance and value.pk == instance.pk:
            raise serializers.ValidationError("Une tâche ne peut pas être son propre parent.")
        return value

    def _ensure_task_type(self, validated_data):
        if validated_data.get("task_type") is None:
            validated_data["task_type"] = TaskType.get_default()
        return validated_data

    def create(self, validated_data):
        validated_data = self._ensure_task_type(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._ensure_task_type(validated_data)
        return super().update(instance, validated_data)


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


class TaskSerializer_api(TaskSerializer):
    pass


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