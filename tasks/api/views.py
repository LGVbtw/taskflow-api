from rest_framework import viewsets, filters, permissions, status, parsers
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from django.template.response import TemplateResponse
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from tasks.models import Task, Need, Message, TaskRelation, Project, Attachment
from tasks.serializers import (
    TaskSerializer as TaskSerializer_api_import,
    NeedSerializer as NeedSerializer_api_import,
    MessageSerializer as MessageSerializer_api_import,
    MessageCreateSerializer as MessageCreateSerializer_api_import,
    TaskRelationSerializer as TaskRelationSerializer_api_import,
    AttachmentSerializer as AttachmentSerializer_api_import,
)

# Rebind expected names to the imported serializers (keeps rest of the file unchanged)
TaskSerializer = TaskSerializer_api_import
NeedSerializer = NeedSerializer_api_import
MessageSerializer = MessageSerializer_api_import
MessageCreateSerializer = MessageCreateSerializer_api_import
TaskRelationSerializer = TaskRelationSerializer_api_import
AttachmentSerializer = AttachmentSerializer_api_import
from tasks.exceptions import TaskInProgressDeletionError
from tasks.services.needs import convert_need


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all().order_by('-id')
    serializer_class = TaskSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['title', 'status', 'task_type__label', 'task_type__code']
    ordering_fields = ['created_at', 'title', 'task_type__order']
    filterset_fields = ['status', 'task_type__code', 'parent', 'priority', 'module', 'target_version', 'project']

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        task = serializer.save(owner=user, reporter=user)
        msg = self.request.data.get('initial_message')
        if msg:
            Message.objects.create(content=msg, author=user if user and user.is_authenticated else None, task=task)

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        if task.status == 'En cours':
            raise TaskInProgressDeletionError()
        return super().destroy(request, *args, **kwargs)

    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='upload',
        url_name='upload',
        parser_classes=[parsers.MultiPartParser, parsers.FormParser],
        renderer_classes=[JSONRenderer, BrowsableAPIRenderer],
    )
    def upload(self, request, pk=None):
        task = self.get_object()
        if request.method == 'GET':
            return TemplateResponse(request, 'attachments/upload_form.html', {'task': task})
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'detail': 'Aucun fichier fourni (champ "file").'}, status=status.HTTP_400_BAD_REQUEST)

        attachment = Attachment(task=task, file=uploaded_file)
        attachment.full_clean()
        attachment.save()
        serializer = AttachmentSerializer(attachment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NeedViewSet(viewsets.ModelViewSet):
    queryset = Need.objects.all().order_by('-id')
    serializer_class = NeedSerializer

    def get_permissions(self):
        if self.action == 'destroy':
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        need = serializer.save(owner=user)
        msg = self.request.data.get('initial_message')
        if msg:
            Message.objects.create(content=msg, author=user if user and user.is_authenticated else None, need=need)

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        need = self.get_object()
        if need.converted:
            return Response({'detail': 'Already converted'}, status=status.HTTP_400_BAD_REQUEST)
        # use service to create task and mark need
        task = convert_need(need, request.user if request.user.is_authenticated else None)
        # copy messages
        msgs = need.messages.all().order_by('created_at')
        for m in msgs:
            Message.objects.create(content=m.content, author=m.author, task=task)
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all().order_by('-created_at')
    serializer_class = MessageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        task_id = self.request.query_params.get('task')
        need_id = self.request.query_params.get('need')
        if task_id:
            qs = qs.filter(task_id=task_id)
        if need_id:
            qs = qs.filter(need_id=need_id)
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        user = request.user if request.user.is_authenticated else None
        serializer = MessageCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        if user:
            obj.author = user
        task_id = data.get('task')
        need_id = data.get('need')
        if task_id:
            try:
                obj.task_id = int(task_id)
            except Exception:
                pass
        if need_id:
            try:
                obj.need_id = int(need_id)
            except Exception:
                pass
        obj.save()
        return Response(MessageSerializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        parent = self.get_object()
        user = request.user if request.user.is_authenticated else None
        content = request.data.get('content')
        if not content:
            return Response({'detail': 'content required'}, status=status.HTTP_400_BAD_REQUEST)
        msg = Message.objects.create(content=content, author=user if user else None, task=parent.task, need=parent.need, parent=parent)
        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class TaskRelationViewSet(viewsets.ModelViewSet):
    queryset = TaskRelation.objects.select_related('src_task', 'dst_task').all()
    serializer_class = TaskRelationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['link_type', 'src_task__title', 'dst_task__title']
    ordering_fields = ['created_at']
    filterset_fields = ['link_type', 'src_task', 'dst_task']


class KanbanView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        columns = {"A faire": [], "En cours": [], "Fait": []}
        queryset = Task.objects.all().order_by('created_at')
        serializer_context = {"request": request}
        for status in columns.keys():
            tasks = queryset.filter(status=status)
            columns[status] = TaskSerializer(tasks, many=True, context=serializer_context).data

        other_statuses = queryset.exclude(status__in=columns.keys())
        if other_statuses.exists():
            columns["Autres"] = TaskSerializer(other_statuses, many=True, context=serializer_context).data

        return Response(columns)


class GanttView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        project_id = request.query_params.get('project')
        projects = Project.objects.prefetch_related('tasks').all()
        if project_id:
            projects = projects.filter(id=project_id)

        data = []
        for project in projects:
            tasks_payload = []
            for task in project.tasks.all().order_by('start_date', 'due_date'):
                tasks_payload.append({
                    "id": task.id,
                    "title": task.title,
                    "start_date": task.start_date.isoformat() if task.start_date else None,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "progress": task.progress,
                })

            data.append({
                "id": project.id,
                "title": project.name,
                "description": project.description,
                "tasks": tasks_payload,
            })

        # Inclure les tâches sans projet pour faciliter l'intégration front
        unassigned_tasks = Task.objects.filter(project__isnull=True)
        if unassigned_tasks.exists():
            data.append({
                "id": None,
                "title": "Sans projet",
                "description": "Tâches non affectées",
                "tasks": [
                    {
                        "id": task.id,
                        "title": task.title,
                        "start_date": task.start_date.isoformat() if task.start_date else None,
                        "due_date": task.due_date.isoformat() if task.due_date else None,
                        "progress": task.progress,
                    }
                    for task in unassigned_tasks
                ],
            })

        return Response({"projects": data})
