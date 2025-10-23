#!/usr/bin/env python3
"""Génère un fichier JSON avec les métriques API extraites de logs/taskflow.log.

Usage:
    python scripts/generate_api_metrics.py

Sortie:
    logs/api_metrics.json

Format de sortie exemple:
{
  "generated_at": "2025-10-23T09:00:00Z",
  "endpoints": {
    "/api/tasks/": {
      "count": 123,
      "avg_ms": 45.3,
      "p90_ms": 120,
      "p95_ms": 200,
      "error_rate": 0.8,
      "error_rate_5xx": 0.2
    }
  }
}
"""
from pathlib import Path
import re
import statistics
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / 'logs' / 'taskflow.log'
OUT = ROOT / 'logs' / 'api_metrics.json'

if not LOG.exists():
    print(f"Fichier log introuvable: {LOG}")
    raise SystemExit(1)

pattern = re.compile(r"\[metrics\].*path:(?P<path>\S+).*status:(?P<status>\d+).*duration_ms:(?P<d>\d+)")

data = {}
with open(LOG, encoding='utf-8') as f:
    for line in f:
        m = pattern.search(line)
        if not m:
            continue
        path = m.group('path')
        status = int(m.group('status'))
        duration = int(m.group('d'))
        entry = data.setdefault(path, {'durations': [], 'count': 0, 'errors': 0, 'errors_5xx': 0})
        entry['durations'].append(duration)
        entry['count'] += 1
        if status >= 400:
            entry['errors'] += 1
        if status >= 500:
            entry['errors_5xx'] += 1

result = {
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'endpoints': {},
}

# Descriptions visibles (commentaires intégrés) : elles seront écrites dans le JSON
field_descriptions = {
    'count': "Nombre total de requêtes observées pour l'endpoint dans le fichier de log.",
    'avg_ms': "Durée moyenne des requêtes en millisecondes.",
    'p90_ms': "90ème percentile des durées (ms) — 90% des requêtes sont plus rapides que cette valeur.",
    'p95_ms': "95ème percentile des durées (ms).",
    'error_rate_percent': "Pourcentage de requêtes ayant renvoyé un code d'erreur (status >= 400).",
    'error_rate_5xx_percent': "Pourcentage de requêtes ayant renvoyé un code d'erreur serveur (status >= 500).",
}
for path, v in data.items():
    durations = v['durations']
    count = v['count']
    avg = float(sum(durations)) / count if count else 0.0
    p90 = int(sorted(durations)[max(0, int(0.9 * count) - 1)]) if count else 0
    p95 = int(sorted(durations)[max(0, int(0.95 * count) - 1)]) if count else 0
    err_rate = (v['errors'] / count) * 100.0 if count else 0.0
    err5_rate = (v['errors_5xx'] / count) * 100.0 if count else 0.0
    result['endpoints'][path] = {
        'count': count,
        'avg_ms': round(avg, 3),
        'p90_ms': p90,
        'p95_ms': p95,
        'error_rate_percent': round(err_rate, 3),
        'error_rate_5xx_percent': round(err5_rate, 3),
        'descriptions': field_descriptions,
    }

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    # Écrire le mapping + une copie des descriptions à la racine pour lisibilité
    output = {
        'generated_at': result['generated_at'],
        'descriptions': field_descriptions,
        'endpoints': result['endpoints'],
    }
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Écrit {OUT} (endpoints: {len(result['endpoints'])})")
