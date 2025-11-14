from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, NeedViewSet, MessageViewSet

router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'needs', NeedViewSet, basename='need')
router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = router.urls
