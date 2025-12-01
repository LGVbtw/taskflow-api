"""Utilities for serving the Task API from a static JSON file (Option A)."""
from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping

from django.conf import settings


class DemoDataUnavailable(RuntimeError):
    """Raised when the demo dataset cannot be loaded."""


def is_demo_mode() -> bool:
    """Return True when the Option A demo mode is enabled."""
    return bool(getattr(settings, "TASKFLOW_USE_DEMO_DATA", False))


def _demo_file_path() -> Path:
    path_value = getattr(settings, "TASKFLOW_DEMO_FILE", settings.BASE_DIR / "demo_tasks.json")
    return Path(path_value)


@lru_cache(maxsize=1)
def load_demo_tasks() -> List[Dict[str, Any]]:
    path = _demo_file_path()
    if not path.exists():
        raise DemoDataUnavailable(f"Fichier de démo introuvable : {path}")
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise DemoDataUnavailable("Le fichier demo_tasks.json doit contenir une liste JSON")
    return payload


def reset_cache() -> None:
    """Clear the cached payload (used by tests when overriding settings)."""
    load_demo_tasks.cache_clear()  # type: ignore[attr-defined]


def _match(value: str | None, target: str | None) -> bool:
    return (value or "").lower() == (target or "").lower()


def _contains(haystack: str | None, needle: str | None) -> bool:
    return (needle or "").lower() in (haystack or "").lower()


def query_demo_tasks(params: Mapping[str, str]) -> Dict[str, Any]:
    """Return a paginated slice of demo tasks applying a subset of filters."""
    tasks = list(load_demo_tasks())
    search_value = params.get("search")
    if search_value:
        tasks = [t for t in tasks if _contains(t.get("title"), search_value) or _contains(t.get("status"), search_value)]
    status = params.get("status")
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    module = params.get("module")
    if module:
        tasks = [t for t in tasks if _match(t.get("module"), module)]
    project = params.get("project")
    if project:
        tasks = [t for t in tasks if str(t.get("project_id") or "") == str(project)]
    task_type = params.get("task_type__code")
    if task_type:
        tasks = [t for t in tasks if _match(t.get("task_type_code"), task_type)]

    ordering = params.get("ordering") or "-created_at"
    reverse = ordering.startswith("-")
    key_name = ordering.lstrip("-")
    tasks.sort(key=lambda item: item.get(key_name) or "", reverse=reverse)

    page_size = int(params.get("page_size") or settings.REST_FRAMEWORK.get("PAGE_SIZE", 5))
    if page_size <= 0:
        page_size = len(tasks) or 1
    page = int(params.get("page") or 1)
    if page <= 0:
        page = 1
    start = (page - 1) * page_size
    end = start + page_size
    sliced = tasks[start:end]
    count = len(tasks)

    return {
        "count": count,
        "next": None,
        "previous": None,
        "results": sliced,
    }


def get_demo_task(task_id: int | str) -> Dict[str, Any]:
    task_id = int(task_id)
    for task in load_demo_tasks():
        if int(task.get("id")) == task_id:
            return task
    raise DemoDataUnavailable(f"Tâche {task_id} introuvable dans demo_tasks.json")


def build_kanban_payload() -> Dict[str, List[Dict[str, Any]]]:
    columns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for task in load_demo_tasks():
        status = task.get("status") or "Non renseigné"
        columns[status].append(task)
    return dict(columns)


def build_gantt_payload() -> Dict[str, Any]:
    projects: Dict[str, Dict[str, Any]] = {}
    for task in load_demo_tasks():
        project_id = task.get("project_id")
        project_name = task.get("project") or "Sans projet"
        key = project_id if project_id is not None else f"none-{project_name}"
        project_block = projects.setdefault(
            key,
            {
                "id": project_id,
                "title": project_name,
                "description": "Tâches regroupées (données démo)",
                "tasks": [],
            },
        )
        project_block["tasks"].append(
            {
                "id": task.get("id"),
                "title": task.get("title"),
                "start_date": task.get("start_date"),
                "due_date": task.get("due_date"),
                "progress": task.get("progress"),
            }
        )
    return {"projects": list(projects.values())}


def build_filter_metadata() -> Dict[str, Any]:
    tasks = load_demo_tasks()
    task_types: Dict[str, str] = {}
    modules = set()
    statuses = set()
    projects: Dict[int | None, str] = {}
    for task in tasks:
        code = task.get("task_type_code")
        label = task.get("task_type_label")
        if code and label:
            task_types[code] = label
        module = task.get("module")
        if module:
            modules.add(module)
        status = task.get("status")
        if status:
            statuses.add(status)
        project_id = task.get("project_id")
        project_name = task.get("project")
        if project_name is not None:
            projects[project_id] = project_name
    return {
        "task_types": [
            {"code": code, "label": task_types[code]}
            for code in sorted(task_types.keys())
        ],
        "modules": sorted(modules),
        "statuses": sorted(statuses),
        "projects": [
            {"id": project_id, "name": name}
            for project_id, name in sorted(projects.items(), key=lambda item: (item[1] or ""))
        ],
    }