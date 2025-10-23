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
from .models import Task
from .serializers import TaskSerializer
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
    search_fields = ["title", "status"]
    ordering_fields = ["created_at", "title"]
    filterset_fields = ["status"]

    def perform_create(self, serializer):
        """Assigne le propriétaire authentifié lors de la création d'une Task.

        Si la requête n'est pas authentifiée, `owner` est enregistré comme None.
        """
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(owner=user)

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
        serializer.save(owner=user)

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
        task = Task.objects.create(
            title=need.title,
            status='A faire',
            owner=need.owner
        )
        need.mark_converted(user=request.user if request.user.is_authenticated else None)
        from .serializers import TaskSerializer
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)
