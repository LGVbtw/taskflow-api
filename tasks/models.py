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


class Task(models.Model):
    """Modèle Task simple.

    Champs :
        - title (str) : Titre de la tâche (max 200 caractères).
        - status (str) : Statut lisible par l'humain ; validé par `validate_status`.
        - created_at (datetime) : Horodatage automatique de création.
        - owner (User|None) : FK optionnelle vers le modèle User de Django. Si
          l'utilisateur est supprimé, le champ est mis à NULL (on_delete=SET_NULL).

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

    def __str__(self):
        """Retourne une représentation compacte lisible de la Task.

        Exemple : "Acheter du lait - alice" ou "Acheter du lait - No Owner" si
        le propriétaire est absent.
        """
        return f"{self.title} - {self.owner.username if self.owner else 'No Owner'}"