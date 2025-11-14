from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, NeedViewSet, MessageViewSet, TaskRelationViewSet

router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'needs', NeedViewSet, basename='need')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'task-relations', TaskRelationViewSet, basename='task-relation')

urlpatterns = router.urls
