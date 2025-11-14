"""
Modèles pour les tâches.

Ce module définit le modèle Task utilisé par l'API. Une Task représente
un élément de travail avec un titre, un statut et un propriétaire
optionnel (utilisateur Django).

Les valeurs de statut autorisées sont : "A faire", "En cours", "Fait".
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone


def validate_status(value):
    """Valide qu'un statut de tâche fait partie des valeurs autorisées.

    Args:
        value (str): Le statut à valider.

    Raises:
        ValidationError: Si `value` n'est pas l'un des statuts autorisés.

    Valeurs autorisées : "A faire", "En cours", "Fait".
    """
    if value not in ["A faire", "En cours", "Fait"]:
        raise ValidationError(f'Statut invalide, veuillez choisir : "A faire", "En cours", "Fait"')


class TaskType(models.Model):
    """Type fonctionnel de tâche (Epic, User Story, etc.)."""

    code = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.label} ({self.code})"

    @classmethod
    def get_default(cls):
        obj, _ = cls.objects.get_or_create(
            code="task",
            defaults={"label": "Tâche", "order": 40},
        )
        return obj


class Task(models.Model):
    """Modèle Task simple.

    Champs :
        - title (str) : Titre de la tâche (max 200 caractères).
        - status (str) : Statut lisible par l'humain ; validé par `validate_status`.
        - created_at (datetime) : Horodatage automatique de création.
                - owner (User|None) : FK optionnelle vers le modèle User de Django. Si
                    l'utilisateur est supprimé, le champ est mis à NULL (on_delete=SET_NULL).
                - task_type : FK vers `TaskType` décrivant la nature du travail.
                - parent : lien optionnel vers une autre Task (sous-tâches).

    Comportement :
        - Le statut par défaut est "A faire".
        - La représentation en chaîne contient le titre et le nom d'utilisateur
          du propriétaire si présent, sinon 'No Owner'.
    """
    title = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        default="A faire",
        validators=[validate_status],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    task_type = models.ForeignKey(
        TaskType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tasks",
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
    )

    def __str__(self):
        """Retourne une représentation compacte lisible de la Task.

        Exemple : "Acheter du lait - alice" ou "Acheter du lait - No Owner" si
        le propriétaire est absent.
        """
        task_type_code = self.task_type.code if self.task_type else "no-type"
        return f"{self.title} [{task_type_code}] - {self.owner.username if self.owner else 'No Owner'}"
    
    def clean(self):
        super().clean()
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError({"parent": "Une tâche ne peut pas être son propre parent."})
        if self.parent and self._would_create_cycle(self.parent):
            raise ValidationError({"parent": "Cycle détecté dans la hiérarchie."})
    
    def _would_create_cycle(self, candidate_parent):
        current = candidate_parent
        # remonte les parents jusqu'à la racine
        while current:
            if current.pk == self.pk:
                return True
            current = current.parent
        return False
    
    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Need(models.Model):
    """Modèle représentant un besoin déposé par un utilisateur.

    Une `Need` peut être transformée en `Task` via l'API. Tout le monde peut
    créer un besoin. Seul le staff/admin peut supprimer un besoin.
    """

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='needs')
    converted = models.BooleanField(default=False)
    converted_at = models.DateTimeField(null=True, blank=True)
    converted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='converted_needs')

    def __str__(self):
        return f"{self.title} - {self.owner.username if self.owner else 'No Owner'}"

    def mark_converted(self, user=None):
        self.converted = True
        self.converted_at = timezone.now()
        self.converted_by = user
        self.save()


class Message(models.Model):
    """Message/commentaire lié à une Task ou à un Need.

    Un message peut être une réponse (parent) et est attribué à un auteur (optionnel).
    """
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name='messages')
    need = models.ForeignKey(Need, on_delete=models.CASCADE, null=True, blank=True, related_name='messages')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

    def __str__(self):
        who = self.author.username if self.author else 'anonymous'
        target = f'Task:{self.task_id}' if self.task_id else (f'Need:{self.need_id}' if self.need_id else 'None')
        return f"Msg {self.pk} by {who} on {target}"