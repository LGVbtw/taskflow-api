"""Script d'agrégation des métriques de requête.

Usage:
    python scripts/aggregate_request_metrics.py

Il calcule pour chaque endpoint (path) : count, avg, min, max, median, p90 (ms).
"""

import csv
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / 'logs' / 'request_metrics.csv'

if not CSV.exists():
    print(f"Fichier de métriques introuvable : {CSV}")
    raise SystemExit(1)

data = {}
with open(CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        path = row['path']
        try:
            duration = int(row['duration_ms'])
        except Exception:
            continue
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
