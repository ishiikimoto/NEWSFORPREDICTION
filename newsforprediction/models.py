from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

PressureDirection = Literal["up", "down", "neutral"]
SupplyStatus = Literal["attention", "normal", "unconfirmed"]
MetricCategory = Literal["fuel", "fx", "power", "weather", "demand", "other"]
SensitivityMode = Literal["cooling", "heating", "neutral"]
HigherMeans = Literal["up", "down", "neutral"]
EventImpact = Literal["up", "down", "neutral", "uncertain"]


@dataclass(slots=True)
class MetricInput:
    name: str
    category: MetricCategory
    current: float
    previous: float | None = None
    week_ago: float | None = None
    unit: str = ""
    higher_means: HigherMeans = "neutral"
    abnormal_daily_pct_threshold: float = 3.0
    comment_hint: str = ""


@dataclass(slots=True)
class WeatherInput:
    region: str
    forecast_temp_c: float
    previous_forecast_temp_c: float | None = None
    normal_temp_c: float | None = None
    sensitivity_mode: SensitivityMode = "cooling"
    abnormal_delta_c_threshold: float = 2.0
    note: str = ""


@dataclass(slots=True)
class DemandInput:
    forecast_gw: float
    previous_forecast_gw: float | None = None
    week_ago_forecast_gw: float | None = None
    abnormal_daily_pct_threshold: float = 4.0
    note: str = ""


@dataclass(slots=True)
class PlantEvent:
    plant_name: str
    status: str
    capacity_mw: float | None = None
    effective_date: str = ""
    confirmed: bool = True
    note: str = ""


@dataclass(slots=True)
class NewsEvent:
    headline: str
    category: str
    impact_direction: EventImpact = "neutral"
    confirmed: bool = True
    note: str = ""


@dataclass(slots=True)
class BriefingInput:
    briefing_date: date
    metrics: list[MetricInput] = field(default_factory=list)
    weather: WeatherInput | None = None
    demand: DemandInput | None = None
    plant_events: list[PlantEvent] = field(default_factory=list)
    news_events: list[NewsEvent] = field(default_factory=list)
    source_notes: list[str] = field(default_factory=list)
    used_sources: list[str] = field(default_factory=list)
    checked_but_unused_sources: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MetricChange:
    name: str
    category: MetricCategory
    unit: str
    current: float
    day_change_value: float | None
    day_change_pct: float | None
    week_change_value: float | None
    week_change_pct: float | None
    abnormal: bool
    comment: str
    directional_score: float = 0.0


@dataclass(slots=True)
class BriefingSummary:
    fuel: PressureDirection
    fx: PressureDirection
    weather_demand: PressureDirection
    supply: SupplyStatus


@dataclass(slots=True)
class BriefingResult:
    briefing_date: date
    summary: BriefingSummary
    movers: list[MetricChange]
    reasons: list[str]
    watch_items: list[str]
    pending_items: list[str]
    used_sources: list[str]
    checked_but_unused_sources: list[str]
