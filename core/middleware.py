import logging
import json
import os
from pathlib import Path
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
        # fichier de métriques JSON maintenu en temps réel
        self.metrics_file = Path(settings.LOGS_DIR) / 'api_metrics.json'
        self.max_samples = 500  # garder les derniers N échantillons par endpoint

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

        # Mettre à jour le fichier JSON de métriques (atomique)
        try:
            # Charger l'existant si présent
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
            else:
                doc = {
                    'generated_at': None,
                    'descriptions': {
                        'count': "Nombre total de requêtes observées pour l'endpoint dans le fichier de log.",
                        'avg_ms': "Durée moyenne des requêtes en millisecondes.",
                        'p90_ms': "90ème percentile des durées (ms) — 90% des requêtes sont plus rapides que cette valeur.",
                        'p95_ms': "95ème percentile des durées (ms).",
                        'error_rate_percent': "Pourcentage de requêtes ayant renvoyé un code d'erreur (status >= 400).",
                        'error_rate_5xx_percent': "Pourcentage de requêtes ayant renvoyé un code d'erreur serveur (status >= 500).",
                    },
                    'endpoints': {}
                }

            ep = doc.setdefault('endpoints', {}).setdefault(path, {})
            # internal fields to maintain state
            dlist = ep.get('_durations', [])
            errors = ep.get('_errors', 0)
            errors5 = ep.get('_errors_5xx', 0)

            # append and trim
            dlist.append(duration_ms)
            if len(dlist) > self.max_samples:
                dlist = dlist[-self.max_samples:]

            if isinstance(status, int):
                if status >= 400:
                    errors += 1
                if status >= 500:
                    errors5 += 1
            else:
                # unknown status, ignore for error counts
                pass

            # recompute aggregated values
            count = ep.get('count', 0) + 1
            avg = float(sum(dlist)) / len(dlist) if dlist else 0.0
            sd = sorted(dlist)
            p90 = int(sd[max(0, int(0.9 * len(sd)) - 1)]) if sd else 0
            p95 = int(sd[max(0, int(0.95 * len(sd)) - 1)]) if sd else 0
            err_rate = (errors / count) * 100.0 if count else 0.0
            err5_rate = (errors5 / count) * 100.0 if count else 0.0

            # write back fields
            ep['_durations'] = dlist
            ep['_errors'] = errors
            ep['_errors_5xx'] = errors5
            ep['count'] = count
            ep['avg_ms'] = round(avg, 3)
            ep['p90_ms'] = p90
            ep['p95_ms'] = p95
            ep['error_rate_percent'] = round(err_rate, 3)
            ep['error_rate_5xx_percent'] = round(err5_rate, 3)
            # include descriptions for consumer clarity
            ep['descriptions'] = doc.get('descriptions')

            doc['generated_at'] = now().isoformat()

            # write atomically but expose a "clean" version (sans champs internes commençant par '_')
            public = {
                'generated_at': doc['generated_at'],
                'descriptions': doc.get('descriptions', {}),
                'endpoints': {}
            }
            for p, info in doc.get('endpoints', {}).items():
                public_info = {}
                for k, v in info.items():
                    if str(k).startswith('_'):
                        continue
                    public_info[k] = v
                public['endpoints'][p] = public_info

            tmp = str(self.metrics_file) + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(public, f, ensure_ascii=False, indent=2)
            os.replace(tmp, str(self.metrics_file))
        except Exception:
            logger.exception('Impossible de mettre à jour api_metrics.json')

        # Log lisible(s) supplémentaires si besoin
        logger.debug(f'[user:{user}] [method:{method}] [path:{path}] [status:{status}] [duration:{duration_ms}ms]')

        return response
