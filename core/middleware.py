import csv
import logging
import os
from django.utils.timezone import now
from django.conf import settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Middleware qui mesure la durée d'une requête et stocke des métriques.

    - Mesure le temps entre le début et la fin de la requête.
    - Ajoute deux headers de réponse :
        - `X-Request-Duration-ms` : durée en millisecondes (entier)
        - `X-Process-Time` : durée en secondes (float, 6 décimales)
    - Ajoute une ligne CSV dans `logs/request_metrics.csv` avec :
        timestamp, method, path, user, status, duration_ms

    Le middleware tolère les erreurs d'écriture pour ne pas casser la requête.
    """

    CSV_FILENAME = settings.LOGS_DIR / 'request_metrics.csv'
    CSV_HEADER = ['timestamp', 'method', 'path', 'user', 'status', 'duration_ms']

    def __init__(self, get_response):
        self.get_response = get_response
        # S'assurer que le fichier CSV existe et a un en-tête
        try:
            if not os.path.exists(self.CSV_FILENAME):
                with open(self.CSV_FILENAME, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.CSV_HEADER)
        except Exception:
            logger.exception('Impossible de préparer le fichier de métriques')

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
            # ne pas casser la requête si on ne peut pas modifier la réponse
            logger.debug('Impossible d ajouter le header X-Request-Duration-ms')

        # Ecrire la métrique en CSV (append), tolérer les erreurs
        try:
            with open(self.CSV_FILENAME, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([now().isoformat(), method, path, user, status, duration_ms])
        except Exception:
            logger.exception('Impossible d ecrire la métrique de requête')

        # Log lisible en parallèle
        logger.info(f'[user:{user}] [method:{method}] [path:{path}] [status:{status}] [duration:{duration_ms}ms]')

        return response
