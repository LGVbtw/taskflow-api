from django.contrib import admin
from .models import Task, Need
from .models import Message
from django.urls import path
from django.utils.html import format_html
from django.shortcuts import redirect, render
from django.contrib import messages
from django.urls import reverse
from django import forms
import logging
import json
from datetime import datetime
from django.conf import settings
from pathlib import Path
from django.http import HttpResponse, Http404
from .services.commits import commits_dir, create_commit, list_commits, load_snapshot, activate_commit
from .services.needs import convert_need, convert_needs


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

    # Utiliser un ModelForm personnalisé pour exposer un champ non-model 'initial_message'
    class TaskAdminForm(forms.ModelForm):
        initial_message = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows':3}), help_text='Message initial associé à la tâche (optionnel)')

        class Meta:
            model = Task
            fields = '__all__'

    form = TaskAdminForm

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
            user_name = request.user.username if request.user and request.user.is_authenticated else 'anonymous'
            user_obj = request.user if request.user and request.user.is_authenticated else None
            logger = logging.getLogger(__name__)
            logger.info(f"[admin-create] user={user_name} task_id={obj.pk} title={obj.title}")
            # Si un message initial a été fourni via le ModelForm, le créer proprement
            try:
                initial_msg = None
                if hasattr(form, 'cleaned_data'):
                    initial_msg = form.cleaned_data.get('initial_message')
                # fallback to POST if necessary
                if not initial_msg:
                    initial_msg = request.POST.get('initial_message')
                if initial_msg:
                    from .models import Message
                    Message.objects.create(content=initial_msg, author=user_obj, task=obj)
            except Exception:
                logger.exception('Erreur lors de la création du message initial en admin')

    # --- Commit management ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('commits/', self.admin_site.admin_view(self.commits_view), name='tasks_commits'),
            path('commits/download/<path:fname>/', self.admin_site.admin_view(self.commits_download), name='tasks_commits_download'),
            path('commits/activate/', self.admin_site.admin_view(self.commits_activate), name='tasks_commits_activate'),
        ]
        return custom_urls + urls

    def commits_view(self, request):
        """Affiche la page de gestion des commits (create/list/select) en délégant au service."""
        d = commits_dir()
        files = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)

        if request.method == 'POST' and 'create_commit' in request.POST:
            name = request.POST.get('commit_name') or 'unnamed'
            fname = create_commit(name, request.user)
            messages.success(request, f"Commit créé: {fname}")
            return redirect(reverse('admin:tasks_commits'))

        # Read active commit pointer if exists
        active = None
        active_file = d.parent / 'active_commit.txt'
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
        d = commits_dir()
        path = d / fname
        if not path.exists():
            raise Http404('Commit not found')
        with open(path, 'rb') as f:
            data = f.read()
        resp = HttpResponse(data, content_type='application/json')
        resp['Content-Disposition'] = f'attachment; filename="{fname}"'
        return resp

    def commits_activate(self, request):
        d = commits_dir()
        fname = request.POST.get('activate_fname')
        path = d / fname
        if not path.exists():
            messages.error(request, 'Version introuvable')
            return redirect(reverse('admin:tasks_commits'))
        try:
            summary = activate_commit(path, request.user)
        except Exception as e:
            messages.error(request, f'Erreur activation du commit: {e}')
            return redirect(reverse('admin:tasks_commits'))

        messages.success(request, (f"Version activée: {summary.get('fname')} — Users: +{summary.get('created_users')}/~{summary.get('updated_users')}, "
                                    f"Tasks: +{summary.get('created_tasks')}/~{summary.get('updated_tasks')} (deleted {summary.get('deleted_tasks')}), "
                                    f"Needs: +{summary.get('created_needs')}/~{summary.get('updated_needs')} (deleted {summary.get('deleted_needs')})"))
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

            # Déléguer la conversion au service
            task = convert_need(need, request.user)
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

            # utiliser le service qui gère l'atomicité
            converted_count = convert_needs(queryset, request.user)
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
