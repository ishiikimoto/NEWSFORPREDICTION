from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass(slots=True)
class HistoryStore:
    path: Path
    payload: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "HistoryStore":
        target = Path(path)
        if target.exists():
            payload = json.loads(target.read_text(encoding="utf-8"))
        else:
            payload = {"metrics": {}, "weather": {}, "demand": {}}
        return cls(path=target, payload=payload)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_previous_value(self, bucket: str, key: str, target_date: date) -> float | None:
        series = self.payload.get(bucket, {}).get(key, {})
        candidates = sorted(item for item in series.keys() if item < target_date.isoformat())
        if not candidates:
            return None
        return float(series[candidates[-1]])

    def get_week_ago_value(self, bucket: str, key: str, target_date: date) -> float | None:
        series = self.payload.get(bucket, {}).get(key, {})
        cutoff = target_date.fromordinal(target_date.toordinal() - 7).isoformat()
        candidates = sorted(item for item in series.keys() if item <= cutoff)
        if not candidates:
            return None
        return float(series[candidates[-1]])

    def record_value(self, bucket: str, key: str, target_date: date, value: float) -> None:
        if bucket not in self.payload:
            self.payload[bucket] = {}
        if key not in self.payload[bucket]:
            self.payload[bucket][key] = {}
        self.payload[bucket][key][target_date.isoformat()] = value
