import logging
from django.utils.timezone import now

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    """Middleware qui journalise chaque requête HTTP.

    Les informations loggées : timestamp, méthode, chemin, utilisateur (username ou Anonymous),
    code de réponse et durée approximative de traitement.

    Le middleware écrit sur le logger du module (configuré dans `LOGGING` pour écrire
    vers la console et le fichier `logs/taskflow.log`).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = now()
        user = request.user.username if hasattr(request, 'user') and request.user and request.user.is_authenticated else 'Anonymous'
        method = request.method
        path = request.get_full_path()

        response = self.get_response(request)

        duration = (now() - start).total_seconds()
        status = getattr(response, 'status_code', 'unknown')

        # Format the message with bracketed fields for easier parsing and
        # consistency: [user:alice] [method:GET] [path:/api/tasks/] [status:200] [duration:0.012s]
        logger.info(
            f"[user:{user}] [method:{method}] [path:{path}] [status:{status}] [duration:{duration:.3f}s] {method} {path}"
        )

        return response
