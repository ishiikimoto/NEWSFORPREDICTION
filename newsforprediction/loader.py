from __future__ import annotations

import json
from datetime import date

from .models import BriefingInput, DemandInput, MetricInput, NewsEvent, PlantEvent, WeatherInput


def load_input_file(path: str) -> BriefingInput:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return load_input_payload(payload)


def load_input_payload(payload: dict) -> BriefingInput:
    return BriefingInput(
        briefing_date=date.fromisoformat(payload["briefing_date"]),
        metrics=[MetricInput(**item) for item in payload.get("metrics", [])],
        weather=WeatherInput(**payload["weather"]) if payload.get("weather") else None,
        demand=DemandInput(**payload["demand"]) if payload.get("demand") else None,
        plant_events=[PlantEvent(**item) for item in payload.get("plant_events", [])],
        news_events=[NewsEvent(**item) for item in payload.get("news_events", [])],
        source_notes=list(payload.get("source_notes", [])),
        used_sources=list(payload.get("used_sources", [])),
        checked_but_unused_sources=list(payload.get("checked_but_unused_sources", [])),
    )
