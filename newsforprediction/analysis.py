from __future__ import annotations

from .models import (
    BriefingInput,
    BriefingResult,
    BriefingSummary,
    MetricChange,
    MetricInput,
    PressureDirection,
    SupplyStatus,
)


def build_briefing(payload: BriefingInput) -> BriefingResult:
    metric_changes = [_analyze_metric(metric) for metric in payload.metrics]
    weather_score, weather_reasons, weather_watch, weather_pending = _analyze_weather(payload)
    demand_score, demand_reasons, demand_watch = _analyze_demand(payload)
    supply_status, supply_reasons, supply_watch, supply_pending = _analyze_supply(payload)
    news_reasons, news_watch, news_pending, news_scores = _analyze_news(payload)

    reasons = [
        *weather_reasons,
        *demand_reasons,
        *supply_reasons,
        *news_reasons,
    ]
    watch_items = _dedupe(
        [
            *weather_watch,
            *demand_watch,
            *supply_watch,
            *news_watch,
            *_watch_items_from_metrics(metric_changes),
        ]
    )
    pending_items = _dedupe(
        [
            *weather_pending,
            *supply_pending,
            *news_pending,
            *_pending_items_from_metrics(metric_changes),
            *payload.source_notes,
        ]
    )

    fuel_score = sum(change.directional_score for change in metric_changes if change.category == "fuel")
    fx_score = sum(change.directional_score for change in metric_changes if change.category == "fx")
    weather_demand_score = weather_score + demand_score
    supply_metric_score = sum(change.directional_score for change in metric_changes if change.category == "power")
    supply_metric_score += news_scores.get("supply", 0.0)
    fuel_score += news_scores.get("fuel", 0.0)
    fx_score += news_scores.get("fx", 0.0)
    weather_demand_score += news_scores.get("weather_demand", 0.0)

    movers = sorted(
        metric_changes,
        key=lambda item: (
            0 if item.abnormal else 1,
            -abs(item.day_change_pct or 0.0),
            -abs(item.week_change_pct or 0.0),
        ),
    )

    if not reasons:
        reasons.append("主要入力に大きな乖離は見られず、現時点ではベースケース維持。")

    if not pending_items:
        pending_items.append("現時点で判断保留が必要な未確認事項は限定的。")

    summary = BriefingSummary(
        fuel=_classify_pressure(fuel_score),
        fx=_classify_pressure(fx_score),
        weather_demand=_classify_pressure(weather_demand_score),
        supply=_classify_supply_status(supply_status, supply_metric_score),
    )
    return BriefingResult(
        briefing_date=payload.briefing_date,
        summary=summary,
        movers=movers,
        reasons=_dedupe(reasons),
        watch_items=_baseline_watch_items(watch_items),
        pending_items=pending_items,
        used_sources=_dedupe(payload.used_sources),
        checked_but_unused_sources=_dedupe(payload.checked_but_unused_sources),
    )


def _analyze_metric(metric: MetricInput) -> MetricChange:
    day_change_value = _delta(metric.current, metric.previous)
    week_change_value = _delta(metric.current, metric.week_ago)
    day_change_pct = _pct_change(metric.current, metric.previous)
    week_change_pct = _pct_change(metric.current, metric.week_ago)
    abnormal = abs(day_change_pct or 0.0) >= metric.abnormal_daily_pct_threshold
    score = _directional_score(
        metric.higher_means,
        day_change_pct,
        week_change_pct,
        metric.abnormal_daily_pct_threshold,
        abnormal,
    )

    if metric.comment_hint:
        comment = metric.comment_hint
    else:
        comment = _default_metric_comment(metric, day_change_pct)

    return MetricChange(
        name=metric.name,
        category=metric.category,
        unit=metric.unit,
        current=metric.current,
        day_change_value=day_change_value,
        day_change_pct=day_change_pct,
        week_change_value=week_change_value,
        week_change_pct=week_change_pct,
        abnormal=abnormal,
        comment=comment,
        directional_score=score,
    )


def _default_metric_comment(metric: MetricInput, day_change_pct: float | None) -> str:
    if day_change_pct is None:
        return "前日比較データが未整備。"

    rising = day_change_pct > 0
    if metric.higher_means == "up":
        return "価格上振れ要因。" if rising else "価格押し下げ要因。"
    if metric.higher_means == "down":
        return "価格押し下げ要因。" if rising else "価格上振れ要因。"
    return "価格影響は中立評価。"


def _analyze_weather(payload: BriefingInput) -> tuple[float, list[str], list[str], list[str]]:
    weather = payload.weather
    if weather is None:
        return 0.0, [], ["気温予報データ"], ["気温予報が未入力。"]

    delta_c = _delta(weather.forecast_temp_c, weather.previous_forecast_temp_c)
    score = 0.0
    reasons: list[str] = []
    watch_items = ["気温予報の更新"]
    pending: list[str] = []

    if delta_c is None:
        pending.append("気温予報の前回値がなく、更新方向をまだ判定できない。")
        return score, reasons, watch_items, pending

    if weather.sensitivity_mode == "cooling":
        score = delta_c * 1.2
        if delta_c >= weather.abnormal_delta_c_threshold:
            reasons.append("気温予報の上方修正により、需要が予測より強く出る可能性。")
        elif delta_c <= -weather.abnormal_delta_c_threshold:
            reasons.append("気温予報の下方修正により、需要が想定より弱含む可能性。")
    elif weather.sensitivity_mode == "heating":
        score = -delta_c * 1.2
        if delta_c <= -weather.abnormal_delta_c_threshold:
            reasons.append("寒波寄りの修正により、暖房需要が強まる可能性。")
        elif delta_c >= weather.abnormal_delta_c_threshold:
            reasons.append("気温上振れで暖房需要が想定を下回る可能性。")

    if weather.normal_temp_c is not None:
        normal_gap = weather.forecast_temp_c - weather.normal_temp_c
        if weather.sensitivity_mode == "cooling" and normal_gap >= 2.0:
            reasons.append("平年比で高温のため、ピーク需要の上振れに注意。")
        elif weather.sensitivity_mode == "heating" and normal_gap <= -2.0:
            reasons.append("平年比で低温のため、需要上振れの継続に注意。")

    return score, reasons, watch_items, pending


def _analyze_demand(payload: BriefingInput) -> tuple[float, list[str], list[str]]:
    demand = payload.demand
    if demand is None:
        return 0.0, [], ["電力需要実績"]

    day_pct = _pct_change(demand.forecast_gw, demand.previous_forecast_gw)
    week_pct = _pct_change(demand.forecast_gw, demand.week_ago_forecast_gw)
    score = 0.0
    reasons: list[str] = []
    watch_items = ["電力需要実績"]

    if day_pct is not None:
        score += day_pct / max(demand.abnormal_daily_pct_threshold, 0.1) * 2.0
        if day_pct >= demand.abnormal_daily_pct_threshold:
            reasons.append("需要見通しが前日比で大きく上昇しており、需給ひっ迫方向。")
        elif day_pct <= -demand.abnormal_daily_pct_threshold:
            reasons.append("需要見通しが前日比で低下しており、需給はやや緩和方向。")
    if week_pct is not None and abs(week_pct) >= demand.abnormal_daily_pct_threshold:
        reasons.append("需要見通しの週次変化も大きく、直近トレンドの再点検が必要。")

    return score, reasons, watch_items


def _analyze_supply(payload: BriefingInput) -> tuple[SupplyStatus, list[str], list[str], list[str]]:
    if not payload.plant_events:
        return "normal", [], ["発電所停止情報"], []

    reasons: list[str] = []
    watch_items = ["発電所停止情報"]
    pending: list[str] = []
    has_attention = False
    has_unconfirmed = False

    for event in payload.plant_events:
        if not event.confirmed:
            has_unconfirmed = True
            pending.append(f"{event.plant_name} の {event.status} 情報が未確認。")
        if event.status.lower() in {"stop", "outage", "shutdown"}:
            has_attention = True
            reasons.append(f"{event.plant_name} の停止で供給余力低下の可能性。")
        if event.status.lower() in {"restart", "resumed", "online"}:
            reasons.append(f"{event.plant_name} の再稼働で供給面は改善方向。")

    if has_unconfirmed:
        return "unconfirmed", _dedupe(reasons), watch_items, _dedupe(pending)
    if has_attention:
        return "attention", _dedupe(reasons), watch_items, pending
    return "normal", _dedupe(reasons), watch_items, pending


def _analyze_news(payload: BriefingInput) -> tuple[list[str], list[str], list[str], dict[str, float]]:
    reasons: list[str] = []
    watch_items: list[str] = []
    pending: list[str] = []
    scores = {"fuel": 0.0, "fx": 0.0, "weather_demand": 0.0, "supply": 0.0}

    for event in payload.news_events:
        watch_items.append(event.headline)
        if not event.confirmed or event.impact_direction == "uncertain":
            pending.append(f"{event.headline} の価格影響はまだ評価保留。")
            continue

        if event.impact_direction == "up":
            reasons.append(f"{event.headline} は上振れ材料。")
            delta = 1.5
        elif event.impact_direction == "down":
            reasons.append(f"{event.headline} は下振れ材料。")
            delta = -1.5
        else:
            continue

        if event.category in {"fuel", "geopolitics"}:
            scores["fuel"] += delta
        elif event.category == "fx":
            scores["fx"] += delta
        elif event.category in {"weather", "demand"}:
            scores["weather_demand"] += delta
        elif event.category in {"policy", "supply"}:
            scores["supply"] += delta

    return _dedupe(reasons), _dedupe(watch_items), _dedupe(pending), scores


def _watch_items_from_metrics(changes: list[MetricChange]) -> list[str]:
    items: list[str] = []
    for change in changes:
        if not change.abnormal:
            continue
        if change.category == "fx":
            items.append("為替")
        elif change.category == "power":
            items.append("JEPX価格")
        elif change.name.lower() in {"brent", "wti"} or "原油" in change.name:
            items.append("原油価格")
        elif change.name.lower() in {"jkm", "lng", "coal"} or "石炭" in change.name:
            items.append("LNG・石炭価格")
        else:
            items.append(change.name)
    return items


def _pending_items_from_metrics(changes: list[MetricChange]) -> list[str]:
    items: list[str] = []
    for change in changes:
        if change.day_change_pct is None:
            items.append(f"{change.name} の前日比が計算できず、短期方向感は保留。")
        if change.week_change_pct is None:
            items.append(f"{change.name} の週次比較がなく、トレンド確認は保留。")
    return items


def _classify_pressure(score: float) -> PressureDirection:
    if score >= 1.5:
        return "up"
    if score <= -1.5:
        return "down"
    return "neutral"


def _classify_supply_status(status: SupplyStatus, score: float) -> SupplyStatus:
    if status == "unconfirmed":
        return "unconfirmed"
    if status == "attention":
        return "attention"
    if score >= 1.5:
        return "attention"
    return "normal"


def _directional_score(
    higher_means: str,
    day_change_pct: float | None,
    week_change_pct: float | None,
    abnormal_daily_pct_threshold: float,
    abnormal: bool,
) -> float:
    if higher_means == "neutral":
        return 0.0

    score = 0.0
    threshold = max(abnormal_daily_pct_threshold, 0.1)
    if day_change_pct is not None:
        score += day_change_pct / threshold
    if week_change_pct is not None:
        score += week_change_pct / (threshold * 2.0)
    if abnormal:
        score *= 1.2
    if higher_means == "down":
        score *= -1.0
    return score


def _delta(current: float, reference: float | None) -> float | None:
    if reference is None:
        return None
    return current - reference


def _pct_change(current: float, reference: float | None) -> float | None:
    if reference in (None, 0):
        return None
    return (current - reference) / reference * 100.0


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _baseline_watch_items(extras: list[str]) -> list[str]:
    baseline = [
        "気温予報の更新",
        "LNG・石炭価格",
        "JEPX価格",
        "電力需要実績",
        "発電所停止情報",
    ]
    return _dedupe([*baseline, *extras])[:8]
