from rest_framework import status
from rest_framework.exceptions import APIException


class TaskInProgressDeletionError(APIException):
    """Raised when attempting to delete a task that is still in progress."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "La suppression est interdite : la tâche est encore en cours."
    )
    default_code = "task_in_progress"
