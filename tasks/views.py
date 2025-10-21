from rest_framework.viewsets import ModelViewSet
from rest_framework import filters 
from .models import Task 
from .serializers import TaskSerializer
from django_filters.rest_framework import DjangoFilterBackend

class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all().order_by('-id')
    serializer_class = TaskSerializer
    filter_backends = [ filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['title', 'status']
    ordering_fields = ['created_at', 'title']
    filterset_fields = ['status']
