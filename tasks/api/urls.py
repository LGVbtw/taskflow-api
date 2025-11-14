from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
	TaskViewSet,
	NeedViewSet,
	MessageViewSet,
	TaskRelationViewSet,
	KanbanView,
	GanttView,
)

router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'needs', NeedViewSet, basename='need')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'task-relations', TaskRelationViewSet, basename='task-relation')

urlpatterns = [
	path('tasks/kanban/', KanbanView.as_view(), name='task-kanban'),
	path('tasks/gantt/', GanttView.as_view(), name='task-gantt'),
]

urlpatterns += router.urls
