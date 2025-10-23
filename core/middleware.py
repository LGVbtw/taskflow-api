import logging
from django.utils.timezone import now
from django.conf import settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Middleware minimal de mesure de durée.

    - Mesure le temps d'une requête, ajoute les headers `X-Request-Duration-ms` et
      `X-Process-Time` à la réponse.
    - Écrit une ligne de log structurée dans le logger (ex. `logs/taskflow.log`) au niveau INFO
      au format :
        [metrics] timestamp:<iso> method:<METHOD> path:<PATH> user:<USER> status:<STATUS> duration_ms:<MS>

    L'objectif : n'utiliser qu'un seul fichier de log (`taskflow.log`) pour les métriques.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = now()
        user = (
            request.user.username
            if hasattr(request, 'user') and request.user and request.user.is_authenticated
            else 'Anonymous'
        )
        method = request.method
        path = request.get_full_path()

        response = self.get_response(request)

        duration_seconds = (now() - start).total_seconds()
        duration_ms = int(duration_seconds * 1000)
        status = getattr(response, 'status_code', 'unknown')

        # Ajoute le header à la réponse
        try:
            response['X-Request-Duration-ms'] = str(duration_ms)
            response['X-Process-Time'] = f"{duration_seconds:.6f}"
        except Exception:
            logger.debug('Impossible d ajouter le header X-Request-Duration-ms')

        # Log formaté pour récupération par scripts
        try:
            logger.info(
                f"[metrics] timestamp:{now().isoformat()} method:{method} path:{path} user:{user} status:{status} duration_ms:{duration_ms}"
            )
        except Exception:
            logger.exception('Impossible d ecrire la métrique dans le log')

        # Log lisible(s) supplémentaires si besoin
        logger.debug(f'[user:{user}] [method:{method}] [path:{path}] [status:{status}] [duration:{duration_ms}ms]')

        return response
