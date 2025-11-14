import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from tasks.models import Task, TaskType


@pytest.mark.django_db
def test_list_tasks_empty_returns_empty_results():
	client = APIClient()

	response = client.get(reverse("task-list"))

	assert response.status_code == 200
	payload = response.json()
	assert payload["count"] == 0
	assert payload["results"] == []


@pytest.mark.django_db
def test_create_task_returns_201_and_created_object():
	client = APIClient()
	body = {"title": "Nouvelle tâche", "status": "A faire"}

	response = client.post(reverse("task-list"), body, format="json")

	assert response.status_code == 201
	payload = response.json()
	assert payload["title"] == body["title"]
	assert payload["status"] == body["status"]
	assert Task.objects.filter(title=body["title"]).exists()


@pytest.mark.django_db
def test_create_task_authenticated_user_sets_owner():
	user = User.objects.create_user(username="alice", password="password123")
	client = APIClient()
	client.force_authenticate(user=user)

	response = client.post(
		reverse("task-list"),
		{"title": "Tâche liée", "status": "A faire"},
		format="json",
	)

	assert response.status_code == 201
	payload = response.json()
	assert payload["owner"] == user.username
	created_task = Task.objects.get(id=payload["id"])
	assert created_task.owner == user


@pytest.mark.django_db
def test_create_task_with_explicit_type():
	client = APIClient()
	body = {
		"title": "Nouvel epic",
		"status": "A faire",
		"task_type_code": "epic",
	}

	response = client.post(reverse("task-list"), body, format="json")

	assert response.status_code == 201
	payload = response.json()
	assert payload["task_type_code"] == "epic"
	assert payload["task_type_label"].lower().startswith("epic")
	created = Task.objects.get(id=payload["id"])
	assert created.task_type.code == "epic"


@pytest.mark.django_db
def test_create_subtask_with_parent():
	client = APIClient()
	feature_type = TaskType.objects.get(code="feature")
	parent = Task.objects.create(title="Parent feature", status="A faire", task_type=feature_type)
	body = {
		"title": "Découpage",
		"status": "A faire",
		"parent": parent.id,
		"task_type_code": "subtask",
	}

	response = client.post(reverse("task-list"), body, format="json")

	assert response.status_code == 201
	payload = response.json()
	assert payload["parent"] == parent.id
	child = Task.objects.get(id=payload["id"])
	assert child.parent == parent
	assert child.task_type.code == "subtask"


@pytest.mark.django_db
def test_create_task_with_unknown_type_fails():
	client = APIClient()
	body = {
		"title": "Erreur type",
		"status": "A faire",
		"task_type_code": "unknown",
	}

	response = client.post(reverse("task-list"), body, format="json")

	assert response.status_code == 400
	assert "task_type_code" in response.json()


@pytest.mark.django_db
def test_update_parent_rejects_cycle():
	client = APIClient()
	type_task = TaskType.objects.get(code="task")
	root = Task.objects.create(title="Root", status="A faire", task_type=type_task)
	child = Task.objects.create(title="Child", status="A faire", task_type=type_task, parent=root)
	grandchild = Task.objects.create(title="Grand", status="A faire", task_type=type_task, parent=child)

	response = client.patch(
		reverse("task-detail", args=[root.id]),
		{"parent": grandchild.id},
		format="json",
	)

	assert response.status_code == 400
	assert "parent" in response.json()


@pytest.mark.django_db
def test_update_parent_allows_valid_move():
	client = APIClient()
	type_task = TaskType.objects.get(code="task")
	root = Task.objects.create(title="Root", status="A faire", task_type=type_task)
	child = Task.objects.create(title="Child", status="A faire", task_type=type_task)

	response = client.patch(
		reverse("task-detail", args=[child.id]),
		{"parent": root.id},
		format="json",
	)

	assert response.status_code == 200
	child.refresh_from_db()
	assert child.parent == root
