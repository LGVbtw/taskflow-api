"""Services pour la conversion des objets Need en Task.

Fournit :
 - convert_need(need, user) -> Task instance
 - convert_needs(queryset, user) -> count converted

Ces fonctions effectuent la création d'une Task et marquent le Need comme converti.
"""
from django.db import transaction
from tasks.models import Task, Need


def convert_need(need: Need, user):
    """Convertit un Need en Task.

    - Crée une Task avec le titre du Need, statut 'A faire' et le même owner.
    - Marque le Need comme converti via mark_converted(user).
    - Retourne la Task créée.
    """
    with transaction.atomic():
        task = Task.objects.create(title=need.title, status='A faire', owner=need.owner)
        # marque le need comme converti
        need.mark_converted(user=user)
    return task


def convert_needs(queryset, user):
    """Convertit un queryset de Needs en Tasks. Retourne le nombre converti."""
    count = 0
    with transaction.atomic():
        for n in queryset.select_for_update():
            if not n.converted:
                convert_need(n, user)
                count += 1
    return count
