"""Keep protocol failures, fixture results and real-game benchmarks distinct."""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

GROUP_FIELDS = ("backend", "map_name", "opponent", "opponent_version", "checkpoint", "mode")
RESULTS = ("win", "loss", "draw", "error", "truncated")


def checkpoint_hash(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def append_record(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


def read_records(path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def summarize(records) -> list[dict]:
    groups = {}
    for record in records:
        if not isinstance(record, dict) or record.get("outcome") not in RESULTS:
            raise ValueError("invalid match outcome")
        try:
            key = tuple(record[field] for field in GROUP_FIELDS)
        except KeyError as error:
            raise ValueError(f"missing benchmark provenance: {error}") from error
        if any(not isinstance(value, str) or not value for value in key):
            raise ValueError("benchmark provenance fields must be nonempty strings")
        counts = groups.setdefault(key, Counter())
        counts[record["outcome"]] += 1
    reports = []
    for key, counts in sorted(groups.items()):
        total = sum(counts.values())
        n = counts["win"] + counts["loss"] + counts["draw"]
        rate = counts["win"] / n if n else None
        interval = None
        if n:
            z = 1.959963984540054
            denominator = 1 + z * z / n
            center = (rate + z * z / (2 * n)) / denominator
            radius = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denominator
            interval = [max(0.0, center - radius), min(1.0, center + radius)]
        reports.append(dict(zip(GROUP_FIELDS, key), total=total, completed=n,
                            wins=counts["win"], losses=counts["loss"], draws=counts["draw"],
                            errors=counts["error"], truncations=counts["truncated"],
                            win_rate=rate, win_rate_ci95=interval,
                            failure_rate=(counts["error"] + counts["truncated"]) / total))
    return reports
