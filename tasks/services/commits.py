"""Services utilitaires pour la gestion des commits (snapshots JSON).

Fonctions exposées :
 - commits_dir() -> Path
 - create_commit(name, request_user) -> filename
 - list_commits() -> list[Path]
 - load_snapshot(path) -> dict
 - activate_commit(path, request_user) -> dict summary

Ces fonctions sont atomiques vis-à-vis de la DB où nécessaire.
"""
from pathlib import Path
import json
import uuid
from datetime import datetime
from django.conf import settings


def commits_dir() -> Path:
    base = Path(settings.BASE_DIR)
    d = base / 'backups' / 'commits'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _commit_filename(name: str) -> str:
    safe = ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()
    stamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    uid = uuid.uuid4().hex[:8]
    return f"commit_{stamp}_{uid}_{safe}.json"


def create_commit(name: str, request_user) -> str:
    from tasks.models import Task, Need
    from django.contrib.auth import get_user_model

    User = get_user_model()
    commits = commits_dir()
    fname = _commit_filename(name or 'unnamed')
    tasks = []
    for t in Task.objects.all():
        tasks.append({'id': t.id, 'title': t.title, 'status': t.status, 'created_at': t.created_at.isoformat() if t.created_at else None, 'owner': t.owner.username if t.owner else None})
    needs = []
    for n in Need.objects.all():
        needs.append({'id': n.id, 'title': n.title, 'description': n.description, 'created_at': n.created_at.isoformat() if n.created_at else None, 'owner': n.owner.username if n.owner else None, 'converted': n.converted, 'converted_at': n.converted_at.isoformat() if n.converted_at else None, 'converted_by': n.converted_by.username if n.converted_by else None})
    users = []
    for u in User.objects.all():
        users.append({'id': u.id, 'username': u.username, 'email': u.email, 'is_staff': u.is_staff, 'is_active': u.is_active, 'date_joined': u.date_joined.isoformat() if getattr(u, 'date_joined', None) else None})
    meta = {'created_by': request_user.username if request_user and getattr(request_user, 'is_authenticated', False) else 'anonymous', 'created_at': datetime.utcnow().isoformat() + 'Z', 'name': name}
    data = {'meta': meta, 'tasks': tasks, 'needs': needs, 'users': users}
    path = commits / fname
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return fname


def list_commits():
    d = commits_dir()
    return sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)


def load_snapshot(path: Path) -> dict:
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def activate_commit(path: Path, request_user):
    """Applique le snapshot JSON à la base de données et retourne un résumé."""
    snapshot = load_snapshot(path)
    from django.db import transaction
    from django.contrib.auth import get_user_model
    from tasks.models import Task, Need

    User = get_user_model()

    def parse_iso(s):
        if not s:
            return None
        try:
            if s.endswith('Z'):
                s2 = s[:-1]
                from datetime import datetime as _dt

                dt = _dt.fromisoformat(s2)
                return dt
            return __import__('datetime').datetime.fromisoformat(s)
        except Exception:
            return None

    users_data = snapshot.get('users', [])
    tasks_data = snapshot.get('tasks', [])
    needs_data = snapshot.get('needs', [])

    created_users = updated_users = 0
    created_tasks = updated_tasks = deleted_tasks = 0
    created_needs = updated_needs = deleted_needs = 0

    with transaction.atomic():
        usernames = [u.get('username') for u in users_data if u.get('username')]
        for u in users_data:
            uname = u.get('username')
            if not uname:
                continue
            defaults = {'email': u.get('email', ''), 'is_staff': u.get('is_staff', False), 'is_active': u.get('is_active', True)}
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

        user_map = {u.username: u for u in User.objects.filter(username__in=usernames)}

        task_ids = []
        for t in tasks_data:
            pk = t.get('id')
            owner_name = t.get('owner')
            owner = user_map.get(owner_name) if owner_name else None
            defaults = {'title': t.get('title'), 'status': t.get('status'), 'owner': owner}
            obj, created = Task.objects.update_or_create(pk=pk, defaults=defaults)
            if t.get('created_at'):
                dt = parse_iso(t.get('created_at'))
                if dt:
                    Task.objects.filter(pk=obj.pk).update(created_at=dt)
            if created:
                created_tasks += 1
            else:
                updated_tasks += 1
            task_ids.append(obj.pk)

        need_ids = []
        for n in needs_data:
            pk = n.get('id')
            owner_name = n.get('owner')
            owner = user_map.get(owner_name) if owner_name else None
            converted_by_name = n.get('converted_by')
            converted_by = user_map.get(converted_by_name) if converted_by_name else None
            defaults = {'title': n.get('title'), 'description': n.get('description'), 'owner': owner, 'converted': n.get('converted', False)}
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

        deleted_tasks = Task.objects.exclude(pk__in=task_ids).count()
        Task.objects.exclude(pk__in=task_ids).delete()
        deleted_needs = Need.objects.exclude(pk__in=need_ids).count()
        Need.objects.exclude(pk__in=need_ids).delete()

    # write active pointer
    active_file = commits_dir().parent / 'active_commit.txt'
    active_file.write_text(path.name, encoding='utf-8')

    return {
        'fname': path.name,
        'created_users': created_users,
        'updated_users': updated_users,
        'created_tasks': created_tasks,
        'updated_tasks': updated_tasks,
        'deleted_tasks': deleted_tasks,
        'created_needs': created_needs,
        'updated_needs': updated_needs,
        'deleted_needs': deleted_needs,
    }
