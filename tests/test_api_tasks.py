import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from tasks.models import Task, TaskType, TaskRelation, Project


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
	assert payload["reporter"] == user.username
	created_task = Task.objects.get(id=payload["id"])
	assert created_task.owner == user
	assert created_task.reporter == user


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


@pytest.mark.django_db
def test_create_task_relation_between_two_tasks():
	client = APIClient()
	sketch = Task.objects.create(title="Source", status="A faire")
	destination = Task.objects.create(title="Destination", status="A faire")
	body = {"src_task": sketch.id, "dst_task": destination.id, "link_type": TaskRelation.BLOCKS}

	response = client.post(reverse("task-relation-list"), body, format="json")

	assert response.status_code == 201
	data = response.json()
	assert data["src_task"] == sketch.id
	assert data["dst_task"] == destination.id
	assert data["link_type"] == TaskRelation.BLOCKS
	assert TaskRelation.objects.filter(src_task=sketch, dst_task=destination, link_type=TaskRelation.BLOCKS).exists()


@pytest.mark.django_db
def test_create_task_relation_rejects_self_link():
	client = APIClient()
	task = Task.objects.create(title="Solo", status="A faire")
	body = {"src_task": task.id, "dst_task": task.id, "link_type": TaskRelation.RELATES}

	response = client.post(reverse("task-relation-list"), body, format="json")

	assert response.status_code == 400
	assert "dst_task" in response.json()
	assert TaskRelation.objects.count() == 0


@pytest.mark.django_db
def test_create_task_relation_rejects_duplicates():
	client = APIClient()
	src = Task.objects.create(title="Source", status="A faire")
	dst = Task.objects.create(title="Dest", status="A faire")
	TaskRelation.objects.create(src_task=src, dst_task=dst, link_type=TaskRelation.DEPENDS)
	body = {"src_task": src.id, "dst_task": dst.id, "link_type": TaskRelation.DEPENDS}

	response = client.post(reverse("task-relation-list"), body, format="json")

	assert response.status_code == 400
	assert "non_field_errors" in response.json()
	assert TaskRelation.objects.count() == 1


@pytest.mark.django_db
def test_task_payload_includes_relation_data():
	client = APIClient()
	src = Task.objects.create(title="Source", status="A faire")
	dst = Task.objects.create(title="Dest", status="A faire")
	TaskRelation.objects.create(src_task=src, dst_task=dst, link_type=TaskRelation.BLOCKS)

	response = client.get(reverse("task-detail", args=[src.id]))

	assert response.status_code == 200
	data = response.json()
	assert len(data["relations_out"]) == 1
	assert data["relations_out"][0]["dst_task"] == dst.id
	assert data["relations_in"] == []


@pytest.mark.django_db
def test_create_task_with_metadata_fields():
	client = APIClient()
	body = {
		"title": "Tâche complexe",
		"status": "A faire",
		"priority": "urgent",
		"target_version": "v1.0.0",
		"module": "API",
		"start_date": "2025-11-01",
		"due_date": "2025-11-30",
		"progress": 45,
	}

	response = client.post(reverse("task-list"), body, format="json")

	assert response.status_code == 201
	data = response.json()
	assert data["priority"] == "urgent"
	assert data["target_version"] == "v1.0.0"
	assert data["module"] == "API"
	assert data["start_date"] == "2025-11-01"
	assert data["due_date"] == "2025-11-30"
	assert data["progress"] == 45
	created = Task.objects.get(id=data["id"])
	assert created.priority == Task.PRIORITY_URGENT
	assert created.target_version == "v1.0.0"
	assert created.module == "API"
	assert str(created.start_date) == "2025-11-01"
	assert str(created.due_date) == "2025-11-30"
	assert created.progress == 45


@pytest.mark.django_db
def test_create_task_with_project_by_name():
	client = APIClient()
	project = Project.objects.create(name="API", description="API public")
	body = {"title": "Déploiement", "status": "A faire", "project": project.name}

	response = client.post(reverse("task-list"), body, format="json")

	assert response.status_code == 201
	data = response.json()
	assert data["project"] == project.name
	created = Task.objects.get(id=data["id"])
	assert created.project == project


@pytest.mark.django_db
def test_filter_tasks_by_project():
	client = APIClient()
	p1 = Project.objects.create(name="Auth", description="")
	p2 = Project.objects.create(name="Mobile", description="")
	Task.objects.create(title="Login", status="A faire", project=p1)
	Task.objects.create(title="Push", status="A faire", project=p2)

	response = client.get(reverse("task-list"), {"project": p1.id})

	assert response.status_code == 200
	data = response.json()
	assert data["count"] == 1
	assert data["results"][0]["title"] == "Login"


@pytest.mark.django_db
def test_create_task_rejects_progress_over_100():
	client = APIClient()
	body = {"title": "Invalide", "status": "A faire", "progress": 150}

	response = client.post(reverse("task-list"), body, format="json")

	assert response.status_code == 400
	assert "progress" in response.json()
	assert Task.objects.count() == 0
