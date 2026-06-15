from __future__ import annotations

from .models import BriefingResult, MetricChange


def render_markdown(result: BriefingResult) -> str:
    lines = [f"# 朝会ブリーフィング {result.briefing_date.isoformat()}", ""]

    lines.extend(
        [
            "## 1. 今日の要約",
            f"- 燃料価格：{_pressure_label(result.summary.fuel)}",
            f"- 為替：{_pressure_label(result.summary.fx)}",
            f"- 天候・需要：{_pressure_label(result.summary.weather_demand)}",
            f"- 供給・発電停止：{_supply_label(result.summary.supply)}",
            "",
            "## 2. 前日から大きく動いた指標",
            "| 指標 | 前日比 | 週次変化 | コメント |",
            "|---|---:|---:|---|",
        ]
    )

    for mover in result.movers:
        lines.append(
            "| {name} | {daily} | {weekly} | {comment} |".format(
                name=mover.name,
                daily=_format_change(mover),
                weekly=_format_week_change(mover),
                comment=mover.comment,
            )
        )

    lines.extend(["", "## 3. 予測値が外れそうな理由候補"])
    for reason in result.reasons:
        lines.append(f"- {reason}")

    lines.extend(["", "## 4. 今日見るべきデータ"])
    for index, item in enumerate(result.watch_items, start=1):
        lines.append(f"{index}. {item}")

    lines.extend(["", "## 5. 判断保留すべき点"])
    for item in result.pending_items:
        lines.append(f"- {item}")

    lines.extend(["", "## 6. 参照ソース"])
    lines.append("- 使用したソース")
    for item in result.used_sources:
        lines.append(f"  - {item}")
    if not result.used_sources:
        lines.append("  - なし")

    lines.append("- 確認したが未採用のソース")
    for item in result.checked_but_unused_sources:
        lines.append(f"  - {item}")
    if not result.checked_but_unused_sources:
        lines.append("  - なし")

    return "\n".join(lines)


def _pressure_label(direction: str) -> str:
    labels = {
        "up": "上振れ圧力",
        "down": "下振れ圧力",
        "neutral": "中立",
    }
    return labels[direction]


def _supply_label(status: str) -> str:
    labels = {
        "attention": "注意",
        "normal": "通常",
        "unconfirmed": "未確認",
    }
    return labels[status]


def _format_change(change: MetricChange) -> str:
    if change.day_change_pct is None:
        return "N/A"
    value = change.day_change_value or 0.0
    prefix = "+" if value > 0 else ""
    pct_prefix = "+" if change.day_change_pct > 0 else ""
    return f"{prefix}{value:.2f} ({pct_prefix}{change.day_change_pct:.1f}%)"


def _format_week_change(change: MetricChange) -> str:
    if change.week_change_pct is None:
        return "N/A"
    value = change.week_change_value or 0.0
    prefix = "+" if value > 0 else ""
    pct_prefix = "+" if change.week_change_pct > 0 else ""
    return f"{prefix}{value:.2f} ({pct_prefix}{change.week_change_pct:.1f}%)"
