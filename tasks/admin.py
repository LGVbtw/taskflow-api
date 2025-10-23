from django.contrib import admin
from .models import Task, Need
from .models import Message
from django.urls import path
from django.utils.html import format_html
from django.shortcuts import redirect, render
from django.contrib import messages
from django.urls import reverse
import logging
import os
import json
import uuid
from datetime import datetime
from django.conf import settings
from pathlib import Path
from django.http import HttpResponse, Http404


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour le modèle Task.

    - Affiche l'ID, le titre, le statut et la date de création dans la liste.
    - Permet la recherche par `id`, `title` et `status`.
    - Rendre l'ID cliquable pour accéder rapidement à la page d'édition.
    - Ajoute un filtre par statut et un tri par date de création décroissante.
    """

    def edit_action(self, obj):
        """Affiche un bouton 'Modifier' qui redirige vers la page de modification admin."""
        url = reverse('admin:tasks_task_change', args=[obj.pk])
        return format_html('<a class="button" href="{}">Modifier</a>', url)

    edit_action.short_description = 'Modifier'

    # Insérer la colonne d'action pour modification
    list_display = ('id', 'title', 'edit_action', 'status', 'created_at')
    list_display_links = ('id', 'title')
    # Utiliser un template custom pour la page de liste afin d'ajouter un bouton 'Commits'
    change_list_template = 'admin/tasks/task/change_list.html'

    def save_model(self, request, obj, form, change):
        """Override pour journaliser les modifications effectuées depuis l'admin.

        En cas de modification (change=True), on récupère l'instance précédente,
        on calcule un diff champ par champ, puis on écrit une ligne de log
        contenant l'utilisateur, l'id de la task et les changements effectués.
        En cas de création (change=False), on logge la création.
        """
        logger = logging.getLogger(__name__)

        if change:
            try:
                old = Task.objects.get(pk=obj.pk)
            except Task.DoesNotExist:
                old = None

            # Sauvegarde de l'objet (applique les changements)
            super().save_model(request, obj, form, change)

            changes = {}
            if old is not None:
                # comparer champs simples
                for field in ['title', 'status', 'owner']:
                    old_val = getattr(old, field)
                    new_val = getattr(obj, field)
                    # pour owner, comparer username ou None
                    if field == 'owner':
                        old_repr = old_val.username if old_val else None
                        new_repr = new_val.username if new_val else None
                    else:
                        old_repr = old_val
                        new_repr = new_val

                    if old_repr != new_repr:
                        changes[field] = [old_repr, new_repr]

            if changes:
                user = request.user.username if request.user and request.user.is_authenticated else 'anonymous'
                logger.info(f"[admin-change] user={user} task_id={obj.pk} changes={changes}")
        else:
            # création
            super().save_model(request, obj, form, change)
            user = request.user.username if request.user and request.user.is_authenticated else 'anonymous'
            logger = logging.getLogger(__name__)
            logger.info(f"[admin-create] user={user} task_id={obj.pk} title={obj.title}")

    # --- Commit management ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('commits/', self.admin_site.admin_view(self.commits_view), name='tasks_commits'),
            path('commits/download/<path:fname>/', self.admin_site.admin_view(self.commits_download), name='tasks_commits_download'),
            path('commits/activate/', self.admin_site.admin_view(self.commits_activate), name='tasks_commits_activate'),
        ]
        return custom_urls + urls

    def _commits_dir(self):
        base = Path(settings.BASE_DIR)
        commits_dir = base / 'backups' / 'commits'
        commits_dir.mkdir(parents=True, exist_ok=True)
        return commits_dir

    def _commit_filename(self, name):
        safe = ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        stamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        uid = uuid.uuid4().hex[:8]
        fname = f"commit_{stamp}_{uid}_{safe}.json"
        return fname

    def _snapshot_data(self, request_user):
        """Collecte les données exportables pour tasks, needs et users."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        tasks = []
        for t in Task.objects.all():
            tasks.append({
                'id': t.id,
                'title': t.title,
                'status': t.status,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'owner': t.owner.username if t.owner else None,
            })

        needs = []
        for n in Need.objects.all():
            needs.append({
                'id': n.id,
                'title': n.title,
                'description': n.description,
                'created_at': n.created_at.isoformat() if n.created_at else None,
                'owner': n.owner.username if n.owner else None,
                'converted': n.converted,
                'converted_at': n.converted_at.isoformat() if n.converted_at else None,
                'converted_by': n.converted_by.username if n.converted_by else None,
            })

        users = []
        for u in User.objects.all():
            users.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'is_staff': u.is_staff,
                'is_active': u.is_active,
                'date_joined': u.date_joined.isoformat() if getattr(u, 'date_joined', None) else None,
            })

        meta = {
            'created_by': request_user.username if request_user and request_user.is_authenticated else 'anonymous',
            'created_at': datetime.utcnow().isoformat() + 'Z',
        }

        return {'meta': meta, 'tasks': tasks, 'needs': needs, 'users': users}

    def commits_view(self, request):
        """Affiche la page de gestion des commits (create/list/select)."""
        commits_dir = self._commits_dir()
        files = sorted(commits_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)

        if request.method == 'POST' and 'create_commit' in request.POST:
            name = request.POST.get('commit_name') or 'unnamed'
            fname = self._commit_filename(name)
            data = self._snapshot_data(request.user)
            data['meta']['name'] = name
            path = commits_dir / fname
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messages.success(request, f"Commit créé: {fname}")
            return redirect(reverse('admin:tasks_commits'))

        # Read active commit pointer if exists
        active = None
        active_file = commits_dir.parent / 'active_commit.txt'
        if active_file.exists():
            try:
                active = active_file.read_text(encoding='utf-8').strip()
            except Exception:
                active = None

        rows = []
        for p in files:
            stat = p.stat()
            try:
                with open(p, 'r', encoding='utf-8') as fh:
                    j = json.load(fh)
                name = j.get('meta', {}).get('name')
            except Exception:
                name = ''
            rows.append({'fname': p.name, 'name': name, 'size': stat.st_size, 'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat()})

        context = {
            'rows': rows,
            'active': active,
        }
        return render(request, 'admin/tasks/commits.html', context)

    def commits_download(self, request, fname):
        commits_dir = self._commits_dir()
        path = commits_dir / fname
        if not path.exists():
            raise Http404('Commit not found')
        with open(path, 'rb') as f:
            data = f.read()
        resp = HttpResponse(data, content_type='application/json')
        resp['Content-Disposition'] = f'attachment; filename="{fname}"'
        return resp

    def commits_activate(self, request):
        commits_dir = self._commits_dir()
        fname = request.POST.get('activate_fname')
        path = commits_dir / fname
        if not path.exists():
            messages.error(request, 'Version introuvable')
            return redirect(reverse('admin:tasks_commits'))
        # Charger et appliquer le snapshot
        try:
            with open(path, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)
        except Exception as e:
            messages.error(request, f'Erreur lecture du commit: {e}')
            return redirect(reverse('admin:tasks_commits'))

        from django.db import transaction
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # helper parse ISO (supporte 'Z')
        def parse_iso(s):
            if not s:
                return None
            try:
                if s.endswith('Z'):
                    s2 = s[:-1]
                    dt = datetime.fromisoformat(s2)
                    return dt.replace(tzinfo=None)
                return datetime.fromisoformat(s)
            except Exception:
                return None

        users_data = snapshot.get('users', [])
        tasks_data = snapshot.get('tasks', [])
        needs_data = snapshot.get('needs', [])

        created_users = updated_users = 0
        created_tasks = updated_tasks = deleted_tasks = 0
        created_needs = updated_needs = deleted_needs = 0

        with transaction.atomic():
            # Upsert users by username
            usernames = [u.get('username') for u in users_data if u.get('username')]
            for u in users_data:
                uname = u.get('username')
                if not uname:
                    continue
                defaults = {
                    'email': u.get('email', ''),
                    'is_staff': u.get('is_staff', False),
                    'is_active': u.get('is_active', True),
                }
                obj, created = User.objects.update_or_create(username=uname, defaults=defaults)
                if u.get('date_joined'):
                    dt = parse_iso(u.get('date_joined'))
                    if dt:
                        try:
                            obj.date_joined = dt
                            obj.save(update_fields=['date_joined'])
                        except Exception:
                            pass
                if created:
                    created_users += 1
                else:
                    updated_users += 1

            # Build username->user map
            user_map = {u.username: u for u in User.objects.filter(username__in=usernames)}

            # Upsert tasks (use provided PKs)
            task_ids = []
            for t in tasks_data:
                pk = t.get('id')
                owner_name = t.get('owner')
                owner = user_map.get(owner_name) if owner_name else None
                defaults = {
                    'title': t.get('title'),
                    'status': t.get('status'),
                    'owner': owner,
                }
                obj, created = Task.objects.update_or_create(pk=pk, defaults=defaults)
                # set created_at if provided
                if t.get('created_at'):
                    dt = parse_iso(t.get('created_at'))
                    if dt:
                        Task.objects.filter(pk=obj.pk).update(created_at=dt)
                if created:
                    created_tasks += 1
                else:
                    updated_tasks += 1
                task_ids.append(obj.pk)

            # Upsert needs
            need_ids = []
            for n in needs_data:
                pk = n.get('id')
                owner_name = n.get('owner')
                owner = user_map.get(owner_name) if owner_name else None
                converted_by_name = n.get('converted_by')
                converted_by = user_map.get(converted_by_name) if converted_by_name else None
                defaults = {
                    'title': n.get('title'),
                    'description': n.get('description'),
                    'owner': owner,
                    'converted': n.get('converted', False),
                }
                obj, created = Need.objects.update_or_create(pk=pk, defaults=defaults)
                if n.get('created_at'):
                    dt = parse_iso(n.get('created_at'))
                    if dt:
                        Need.objects.filter(pk=obj.pk).update(created_at=dt)
                if n.get('converted_at'):
                    dt2 = parse_iso(n.get('converted_at'))
                    if dt2:
                        Need.objects.filter(pk=obj.pk).update(converted_at=dt2)
                if converted_by:
                    Need.objects.filter(pk=obj.pk).update(converted_by=converted_by)
                if created:
                    created_needs += 1
                else:
                    updated_needs += 1
                need_ids.append(obj.pk)

            # Delete tasks/needs not present in snapshot to mirror snapshot state
            deleted_tasks = Task.objects.exclude(pk__in=task_ids).count()
            Task.objects.exclude(pk__in=task_ids).delete()
            deleted_needs = Need.objects.exclude(pk__in=need_ids).count()
            Need.objects.exclude(pk__in=need_ids).delete()

        # Write active pointer
        active_file = commits_dir.parent / 'active_commit.txt'
        active_file.write_text(fname, encoding='utf-8')

        messages.success(request, (f'Version activée: {fname} — Users: +{created_users}/~{updated_users}, '
                                    f'Tasks: +{created_tasks}/~{updated_tasks} (deleted {deleted_tasks}), '
                                    f'Needs: +{created_needs}/~{updated_needs} (deleted {deleted_needs})'))
        return redirect(reverse('admin:tasks_commits'))
    search_fields = ('id', 'title', 'status')
    list_filter = ('status',)
    ordering = ('-created_at',)


@admin.register(Need)
class NeedAdmin(admin.ModelAdmin):
        """Admin simple pour les besoins (Need).

        - Affiche id, title, owner, converted et created_at.
        - La suppression dans l'admin reste possible mais la politique applicative
            est que seuls les admins peuvent supprimer ; django admin affiche la
            possibilité si l'utilisateur a les permissions.
        """
        list_display = ('id', 'title', 'owner', 'converted', 'created_at')
        search_fields = ('id', 'title', 'owner__username')
        list_filter = ('converted',)

        actions = ['convert_selected']

        def get_urls(self):
            urls = super().get_urls()
            custom_urls = [
                path('convert/<int:need_id>/', self.admin_site.admin_view(self.convert_view), name='tasks_need_convert'),
            ]
            return custom_urls + urls

        def convert_view(self, request, need_id):
            """Vue admin qui convertit un Need en Task et redirige vers la liste."""
            if not request.user.is_staff:
                messages.error(request, "Permission refusée: seuls les administrateurs peuvent convertir des besoins.")
                return redirect(reverse('admin:tasks_need_changelist'))

            try:
                need = Need.objects.get(pk=need_id)
            except Need.DoesNotExist:
                messages.error(request, "Le besoin demandé n'existe pas.")
                return redirect(reverse('admin:tasks_need_changelist'))

            if need.converted:
                messages.info(request, "Ce besoin a déjà été converti.")
                return redirect(reverse('admin:tasks_need_changelist'))

            # Crée la Task correspondante
            task = Task.objects.create(title=need.title, status='A faire', owner=need.owner)
            need.mark_converted(user=request.user)
            messages.success(request, f"Besoin '{need.title}' converti en tâche (id={task.id}).")
            return redirect(reverse('admin:tasks_need_changelist'))

        def convert_action(self, obj):
            """Affiche un bouton 'Convertir' dans la colonne de la liste."""
            if obj.converted:
                return format_html('<span style="color: #666;">Converti</span>')
            url = reverse('admin:tasks_need_convert', args=[obj.pk])
            return format_html('<a class="button" href="{}">Convertir</a>', url)

        convert_action.short_description = 'Action'

        def convert_selected(self, request, queryset):
            """Action admin qui convertit les besoins sélectionnés en tâches."""
            if not request.user.is_staff:
                self.message_user(request, "Permission refusée: seuls les administrateurs peuvent convertir des besoins.", level=messages.ERROR)
                return

            converted_count = 0
            for need in queryset:
                if not need.converted:
                    Task.objects.create(title=need.title, status='A faire', owner=need.owner)
                    need.mark_converted(user=request.user)
                    converted_count += 1

            self.message_user(request, f"{converted_count} besoin(s) converti(s) en tâche.")

        convert_selected.short_description = 'Convertir les besoins sélectionnés en tâches'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Affiche et administre les messages/commentaires liés aux tasks/needs."""
    list_display = ('id', 'short_content', 'author', 'task', 'need', 'created_at')
    search_fields = ('content', 'author__username')
    readonly_fields = ('created_at',)

    def short_content(self, obj):
        return (obj.content[:75] + '...') if len(obj.content) > 75 else obj.content
    short_content.short_description = 'content'
