# CHANGELOG

Tous les changements notables du projet TaskFlow depuis la "Séance 2 – Construire le socle DRF du projet TaskFlow".

Ce fichier suit un format simple et lisible, centré sur les objectifs pédagogiques et les livrables techniques de la séance.

## Résumé (haut niveau)

- Ajout d'une validation de modèle pour les statuts de tâche afin d'assurer la cohérence des données.
- Introduction d'une relation optionnelle `owner` vers `User` et exposition du nom du propriétaire dans le sérialiseur.
- Activation de la recherche, du tri et du filtrage sur l'API Task, et ajout de docstrings explicatives dans les modèles, sérialiseurs et vues.
- Règle métier : interdiction de supprimer une tâche dont le statut est "En cours" (levée d'une exception personnalisée dans la vue).
- Ajout de tests pytest et de fixtures pour les exercices de la séance (voir `tests/` et `tasks/fixtures/`).

---

## Détails par fonctionnalité / épic

### Épic 2 — Gestion des tâches (CRUD)

- Fichiers modifiés : `tasks/models.py`, `tasks/serializers.py`, `tasks/views.py`, `tasks/tests.py`
- Implémentations :
  - Support CRUD complet via un `ModelViewSet` DRF (`TaskViewSet`).
  - Modèle `Task` avec les champs : `title`, `status`, `created_at`, `owner` (FK vers `auth.User`).
  - À la création d'une tâche, si l'utilisateur est authentifié il est assigné en tant que `owner` ; sinon `owner` reste `null`.

### Épic 2 — Filtres & Recherche

- Fichiers modifiés : `tasks/views.py`
- Implémentations :
  - Activation des filtres DRF : Search (`?search=` sur `title` et `status`), Ordering (`?ordering=` sur `created_at`, `title`) et DjangoFilterBackend (`?status=`).
  - Pagination configurée lors des exercices pour limiter le nombre de résultats par page.

### Épic 3 — Collaboration

- Fichiers modifiés : `tasks/models.py`, `tasks/serializers.py`
- Implémentations :
  - Ajout d'une ForeignKey `owner` optionnelle vers `User` (null=True, on_delete=SET_NULL) pour permettre l'attribution des tâches.
  - Le sérialiseur expose `owner` via `owner.username` (lecture seule) pour une réponse utilisateur-friendly.

### Épic 4 — Qualité & KPIs (tests & fixtures)

- Fichiers ajoutés/modifiés : `tests/`, `tasks/fixtures/demo_tasks.json`
- Implémentations :
  - Pytest configuré pour le projet ; tests de base ajoutés (liste vide, création renvoyant 201, comportement avec authentification).
  - Fixture de démonstration pour insérer rapidement des tâches (`manage.py loaddata tasks/fixtures/demo_tasks.json`).

### Épic 5 — Sécurité (validation & erreurs contrôlées)

- Fichiers modifiés : `tasks/models.py`, `tasks/exceptions.py`, `tasks/views.py`
- Implémentations :
  - Le validateur de modèle `validate_status` impose les valeurs autorisées : "A faire", "En cours", "Fait". Les tentatives invalides renvoient HTTP 400 via DRF.
  - Exception API personnalisée `TaskInProgressDeletionError` levée lors d'une tentative de suppression d'une tâche "En cours" (DRF traduit cela en réponse HTTP appropriée).

---

## Fichiers touchés (non exhaustif)

- `tasks/models.py` — docstrings de modèle et validateur `validate_status`; ajout de la FK `owner`.
- `tasks/serializers.py` — docstrings du sérialiseur ; exposition de `owner.username` en lecture seule.
- `tasks/views.py` — docstrings du viewset ; filtres/recherche/tri activés ; `perform_create` défini pour assigner l'owner ; `destroy` empêche la suppression des tâches "En cours".
- `tasks/exceptions.py` — exception API personnalisée utilisée pour empêcher certaines suppressions.
- `tasks/fixtures/demo_tasks.json` — données de démonstration utilisées pendant la séance.
- `tests/` — tests pytest ajoutés pour valider le CRUD et les règles métier.

---

## Comment reproduire / tester les comportements principaux

1. Créer et activer l'environnement virtuel puis installer les dépendances depuis `requirements.txt`.
2. Appliquer les migrations et charger les données de démonstration :

```powershell
cd 'c:\Cours Ynov\B3\Dev API\Dev\taskflow-api'
python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata tasks/fixtures/demo_tasks.json
```

3. Lancer le serveur et ouvrir l'API Task :

```powershell
python manage.py runserver
# puis ouvrir http://127.0.0.1:8000/api/tasks/
```

4. Tester les règles :
  - Créer une tâche avec `status` = `Terminé` → doit renvoyer 400 car le validateur modèle rejette la valeur.
  - Tenter DELETE sur une tâche avec `status` = `En cours` → doit renvoyer l'erreur personnalisée (interdiction).
  - Utiliser `?search=`, `?status=` et `?ordering=` pour exercer recherche, filtre et tri.

5. Lancer les tests :

```powershell
pytest -q
```

---

## Notes & prochaines étapes

- Priorités restantes :
  - Ajouter authentification/permissions pour que les utilisateurs ne voient/modifient que leurs tâches.
  - Renforcer la suite de tests (tests d'intégration, cas limites) et ajouter CI.
  - Documenter l'API (OpenAPI/Swagger) et fournir des exemples d'appels.
  - Introduire des indicateurs/KPIs et de l'observabilité (logs, métriques, temps de réponse).

- Améliorations immédiates suggérées :
  - Définir des choices explicites pour `status` afin d'améliorer l'expérience admin.
  - Vérifier et centraliser la pagination dans les settings si nécessaire.
  - Ajouter des tests d'intégration pour la règle de suppression.

---

Date : 2025-10-23
