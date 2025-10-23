"""Script d'agrégation des métriques de requête.

Lecture du fichier `logs/taskflow.log` et extraction des lignes commençant par
"[metrics]". Chaque ligne doit contenir `path:<PATH>` et `duration_ms:<MS>`.

Usage:
    python scripts/aggregate_request_metrics.py

Il calcule pour chaque endpoint (path) : count, avg, min, max, median, p90 (ms).
"""

import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / 'logs' / 'taskflow.log'

if not LOG.exists():
    print(f"Fichier de métriques introuvable : {LOG}")
    raise SystemExit(1)

pattern = re.compile(r"\[metrics\].*path:(?P<path>\S+).*duration_ms:(?P<d>\d+)")

data = {}
with open(LOG, encoding='utf-8') as f:
    for line in f:
        m = pattern.search(line)
        if not m:
            continue
        path = m.group('path')
        duration = int(m.group('d'))
        data.setdefault(path, []).append(duration)

print(f"Found {len(data)} endpoints with data\n")
print("path,count,avg_ms,min_ms,max_ms,median_ms,p90_ms")
for path, durations in sorted(data.items(), key=lambda x: -len(x[1])):
    count = len(durations)
    avg = int(sum(durations) / count)
    mn = min(durations)
    mx = max(durations)
    med = int(statistics.median(durations))
    p90 = int(sorted(durations)[int(0.9 * count) - 1]) if count >= 10 else int(sorted(durations)[-1])
    print(f"{path},{count},{avg},{mn},{mx},{med},{p90}")
