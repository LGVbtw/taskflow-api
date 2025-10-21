import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from tasks.models import Task


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
