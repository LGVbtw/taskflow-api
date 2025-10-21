from rest_framework.viewsets import ModelViewSet 
from .models import Task 
from .serializers import TaskSerializer
from rest_framework import filters, pagination
from django_filters.rest_framework import DjangoFilterBackend


class TaskPagination(pagination.PageNumberPagination):
    page_size = 5

class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all().order_by('-id')
    serializer_class = TaskSerializer
    pagination_class = TaskPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['title', 'status']
    ordering_fields = ['id', 'title', 'status', 'created_at']