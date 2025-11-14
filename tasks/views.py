"""
Vues pour l'application des tâches.

Ce module expose un ModelViewSet fournissant les endpoints CRUD standards
pour les objets Task. Il permet la recherche, le tri et le filtrage via
paramètres de requête et applique une règle métier empêchant la suppression
des tâches ayant le statut "En cours".
"""

from rest_framework.viewsets import ModelViewSet
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Task, TaskRelation
from .serializers import TaskSerializer, TaskRelationSerializer
from .models import Message
from .serializers import MessageSerializer, MessageCreateSerializer
from .exceptions import TaskInProgressDeletionError
from .models import Need
from .serializers import NeedSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, AllowAny


class TaskViewSet(ModelViewSet):
    """ViewSet fournissant list, retrieve, create, update et delete pour Task.

    Endpoints (fournis par ModelViewSet) :
        - list : GET /tasks/ -> liste paginée de tâches
        - retrieve : GET /tasks/{pk}/ -> tâche unique
        - create : POST /tasks/ -> création
        - update/partial_update : PUT/PATCH /tasks/{pk}/ -> modification
        - destroy : DELETE /tasks/{pk}/ -> suppression (voir restrictions)

    Fonctionnalités :
        - recherche sur `title` et `status` via `?search=` (DRF SearchFilter).
        - tri via `?ordering=created_at` ou `?ordering=title`.
        - filtrage par statut via `?status=` (DjangoFilterBackend).

    Personnalisations :
        - À la création, si l'utilisateur est authentifié, le champ `owner` est
          défini sur cet utilisateur ; sinon il reste à None.
        - La suppression d'une tâche dont `status` == "En cours" est interdite
          et lève `TaskInProgressDeletionError`.
    """
    queryset = Task.objects.all().order_by("-id")
    serializer_class = TaskSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ["title", "status", "task_type__label", "task_type__code"]
    ordering_fields = ["created_at", "title", "task_type__order"]
    filterset_fields = [
        "status",
        "task_type__code",
        "parent",
        "priority",
        "module",
        "target_version",
        "project",
    ]

    def perform_create(self, serializer):
        """Assigne le propriétaire authentifié lors de la création d'une Task.

        Si la requête n'est pas authentifiée, `owner` est enregistré comme None.
        """
        user = self.request.user if self.request.user.is_authenticated else None
        task = serializer.save(owner=user, reporter=user)
        # Si un message initial est fourni dans le POST payload, créer le message
        msg = self.request.data.get('initial_message')
        if msg:
            Message.objects.create(content=msg, author=user if user and user.is_authenticated else None, task=task)

    def destroy(self, request, *args, **kwargs):
        """Empêche la suppression des tâches marquées "En cours".

        Lève :
            TaskInProgressDeletionError : si le statut de la tâche est "En cours".
        """
        task = self.get_object()
        if task.status == "En cours":
            raise TaskInProgressDeletionError()
        return super().destroy(request, *args, **kwargs)


class NeedViewSet(ModelViewSet):
    """ViewSet pour gérer les besoins (Need).

    - Tout le monde peut créer un Need.
    - Seuls les administrateurs peuvent supprimer un Need.
    - Fournit une action `convert` qui transforme le besoin en Task.
    """
    queryset = Need.objects.all().order_by('-id')
    serializer_class = NeedSerializer

    def get_permissions(self):
        # Creation et lecture ouverts à tous, suppression réservée aux admins
        if self.action == 'destroy':
            return [IsAdminUser()]
        return [AllowAny()]

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        need = serializer.save(owner=user)
        # message initial optionnel
        msg = self.request.data.get('initial_message')
        if msg:
            Message.objects.create(content=msg, author=user if user and user.is_authenticated else None, need=need)

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """Convertit un Need en Task et renvoie la Task créée.

        Le champ `owner` de la Task sera le même que le Need si présent.
        Seule la création de la Task est automatique ; le Need est marqué
        comme converti et reste dans la base pour traçabilité.
        """
        need = self.get_object()
        if need.converted:
            return Response({'detail': 'Already converted'}, status=status.HTTP_400_BAD_REQUEST)

        # Créer la Task correspondante
        reporter = request.user if request.user.is_authenticated else None
        task = Task.objects.create(
            title=need.title,
            status='A faire',
            owner=need.owner,
            reporter=reporter,
        )
        # Si le Need avait des messages, on peut copier le premier message dans la Task en tant qu'historique
        msgs = need.messages.all().order_by('created_at')
        if msgs.exists():
            for m in msgs:
                Message.objects.create(content=m.content, author=m.author, task=task, parent=None)
        need.mark_converted(user=request.user if request.user.is_authenticated else None)
        from .serializers import TaskSerializer
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


from rest_framework import viewsets, permissions


class MessageViewSet(viewsets.ModelViewSet):
    """Endpoints pour créer/lister/répondre aux messages.

    - list : GET /messages/?task={id} ou /messages/?need={id}
    - create : POST /messages/ avec payload {'content','task'|'need', 'parent' (opt)}
    - reply : POST /messages/{pk}/reply/ -> crée une réponse dont l'auteur est l'utilisateur authentifié
    """
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
        # support simple creation: specify task or need in body
        data = request.data.copy()
        user = request.user if request.user.is_authenticated else None
        serializer = MessageCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        # attach author and target if provided
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
