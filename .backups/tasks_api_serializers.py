# Backup of tasks/api/serializers.py
# Created automatically before merging into tasks/serializers.py

from rest_framework import serializers
from tasks.models import Task, Need, Message


class TaskSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Task
        fields = ('id', 'title', 'status', 'created_at', 'owner')


class NeedSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Need
        fields = ('id', 'title', 'description', 'created_at', 'owner', 'converted', 'converted_at', 'converted_by')


class MessageSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source='author.username')

    class Meta:
        model = Message
        fields = ('id', 'content', 'created_at', 'author', 'parent', 'task', 'need')


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ('id', 'content', 'parent', 'task', 'need')
