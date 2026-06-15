from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from .history import HistoryStore
from .models import BriefingInput, DemandInput, MetricInput, NewsEvent, WeatherInput


@dataclass(slots=True)
class OfficialFreeConfig:
    briefing_date: date
    region_name: str
    jma_prefecture_code: str
    jma_temp_area_name: str
    occto_area_code: str
    occto_area_name: str
    history_path: str = "data/history.json"


@dataclass(slots=True)
class HttpClient:
    timeout_seconds: float = 20.0
    user_agent: str = "NewsforPrediction-PoC/0.1"

    def get_text(
        self,
        url: str,
        encoding: str = "utf-8",
        headers: dict[str, str] | None = None,
    ) -> str:
        merged_headers = {"User-Agent": self.user_agent}
        if headers:
            merged_headers.update(headers)
        request = Request(url, headers=merged_headers)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read().decode(encoding, errors="replace")

    def get_json(self, url: str) -> object:
        return json.loads(self.get_text(url))


class _TagTextParser(HTMLParser):
    def __init__(self, tags: set[str]) -> None:
        super().__init__()
        self.tags = tags
        self.current_tag: str | None = None
        self.current_parts: list[str] = []
        self.items: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.tags:
            self.current_tag = tag
            self.current_parts = []

    def handle_data(self, data: str) -> None:
        if self.current_tag:
            self.current_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current_tag == tag:
            text = " ".join(part.strip() for part in self.current_parts if part.strip()).strip()
            if text:
                self.items.append(text)
            self.current_tag = None
            self.current_parts = []


def build_official_free_input(config_path: str) -> BriefingInput:
    config = _load_config(config_path)
    client = HttpClient()
    history = HistoryStore.load(config.history_path)

    metrics: list[MetricInput] = []
    news_events: list[NewsEvent] = []
    source_notes: list[str] = [
        "原油・LNG・石炭の数値価格は今回の無料公式ソース構成では未取得。燃料は制度・需給ニュースの代理評価。",
    ]
    used_sources: list[str] = []
    checked_but_unused_sources: list[str] = [
        "BOJ Foreign Exchange Rates (Daily): 公式ページ確認のみ。PoC では数値抽出未実装または失敗時は未採用。",
        "資源エネルギー庁: タイムアウトまたは該当見出しなしの場合は未採用。",
    ]

    jepx = _safe_fetch(source_notes, "JEPX の取得に失敗。", _fetch_jepx_index, client)
    if jepx is not None:
        used_sources.append("JEPX Spot Index CSV")
        metrics.append(
            _metric_from_history(
                history=history,
                bucket="metrics",
                target_date=config.briefing_date,
                key="JEPX DA-24",
                metric=MetricInput(
                    name="JEPX DA-24",
                    category="power",
                    current=jepx["da24"],
                    unit="JPY/kWh",
                    higher_means="up",
                    abnormal_daily_pct_threshold=8.0,
                    comment_hint="JEPXスポット価格の変動。",
                ),
            )
        )

    occto = _safe_fetch(
        source_notes,
        "OCCTO の需給データ取得に失敗したため、需要・予備率は未確認。",
        _fetch_occto_area_supply_demand,
        client,
        config,
    )
    if occto is not None:
        used_sources.append("OCCTO 広域予備率Web公表システム dailyData")
        metrics.append(
            _metric_from_history(
                history=history,
                bucket="metrics",
                target_date=config.briefing_date,
                key=f"OCCTO {config.occto_area_name} reserve rate",
                metric=MetricInput(
                    name=f"OCCTO {config.occto_area_name} Reserve Rate",
                    category="power",
                    current=occto["min_reserve_rate"],
                    unit="%",
                    higher_means="down",
                    abnormal_daily_pct_threshold=10.0,
                    comment_hint="予備率低下なら需給ひっ迫方向。",
                ),
            )
        )
        demand = _demand_from_history(
            history=history,
            target_date=config.briefing_date,
            key=f"OCCTO {config.occto_area_name} demand forecast",
            forecast_gw=occto["max_demand_gw"],
        )
    else:
        demand = None

    jma = _safe_fetch(
        source_notes,
        "気象庁の予報値取得に失敗したため、気温要因は未確認。",
        _fetch_jma_weather,
        client,
        config,
    )
    if jma is not None:
        used_sources.append(f"気象庁 forecast JSON ({config.jma_prefecture_code})")
        weather = _weather_from_history(
            history=history,
            target_date=config.briefing_date,
            key=f"JMA {config.jma_temp_area_name} forecast temp",
            region=config.region_name,
            forecast_temp_c=jma["forecast_temp_c"],
            normal_temp_c=jma["normal_temp_c"],
        )
    else:
        weather = None

    boj_metric = _safe_fetch(
        source_notes,
        "BOJ の USD/JPY は公式ページ確認までは実装済みだが、PoC では数値抽出失敗時に未確認扱い。",
        _fetch_boj_usdjpy,
        client,
    )
    if boj_metric is not None:
        used_sources.append("BOJ Foreign Exchange Rates (Daily)")
        metrics.append(
            _metric_from_history(
                history=history,
                bucket="metrics",
                target_date=config.briefing_date,
                key="USD/JPY",
                metric=MetricInput(
                    name="USD/JPY",
                    category="fx",
                    current=boj_metric,
                    unit="JPY",
                    higher_means="up",
                    abnormal_daily_pct_threshold=0.7,
                    comment_hint="円安なら燃料費上振れ。",
                ),
            )
        )
    else:
        pass

    enecho_news = _safe_fetch(source_notes, "資源エネルギー庁ニュースの取得に失敗。", _fetch_enecho_news, client) or []
    if enecho_news:
        used_sources.append("資源エネルギー庁トップページ見出し")
        checked_but_unused_sources = [
            item for item in checked_but_unused_sources if not item.startswith("資源エネルギー庁:")
        ]
    news_events.extend(enecho_news)

    nra_news = _safe_fetch(source_notes, "NRA ニュースの取得に失敗。", _fetch_nra_news, client) or []
    if nra_news:
        used_sources.append("NRA トップページ / 発電所別情報導線")
    news_events.extend(nra_news)

    history.save()
    return BriefingInput(
        briefing_date=config.briefing_date,
        metrics=metrics,
        weather=weather,
        demand=demand,
        news_events=news_events,
        source_notes=source_notes,
        used_sources=used_sources,
        checked_but_unused_sources=checked_but_unused_sources,
    )


def _load_config(path: str) -> OfficialFreeConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return OfficialFreeConfig(
        briefing_date=date.fromisoformat(payload["briefing_date"]),
        region_name=payload["region_name"],
        jma_prefecture_code=payload["jma_prefecture_code"],
        jma_temp_area_name=payload["jma_temp_area_name"],
        occto_area_code=payload["occto_area_code"],
        occto_area_name=payload["occto_area_name"],
        history_path=payload.get("history_path", "data/history.json"),
    )


def _safe_fetch(source_notes: list[str], message: str, func, *args):
    try:
        return func(*args)
    except Exception:
        source_notes.append(message)
        return None


def _metric_from_history(
    *,
    history: HistoryStore,
    bucket: str,
    target_date: date,
    key: str,
    metric: MetricInput,
) -> MetricInput:
    metric.previous = history.get_previous_value(bucket, key, target_date)
    metric.week_ago = history.get_week_ago_value(bucket, key, target_date)
    history.record_value(bucket, key, target_date, metric.current)
    return metric


def _weather_from_history(
    *,
    history: HistoryStore,
    target_date: date,
    key: str,
    region: str,
    forecast_temp_c: float,
    normal_temp_c: float | None,
) -> WeatherInput:
    previous = history.get_previous_value("weather", key, target_date)
    history.record_value("weather", key, target_date, forecast_temp_c)
    return WeatherInput(
        region=region,
        forecast_temp_c=forecast_temp_c,
        previous_forecast_temp_c=previous,
        normal_temp_c=normal_temp_c,
        sensitivity_mode="cooling",
        abnormal_delta_c_threshold=1.5,
    )


def _demand_from_history(
    *,
    history: HistoryStore,
    target_date: date,
    key: str,
    forecast_gw: float,
) -> DemandInput:
    previous = history.get_previous_value("demand", key, target_date)
    week_ago = history.get_week_ago_value("demand", key, target_date)
    history.record_value("demand", key, target_date, forecast_gw)
    return DemandInput(
        forecast_gw=forecast_gw,
        previous_forecast_gw=previous,
        week_ago_forecast_gw=week_ago,
        abnormal_daily_pct_threshold=4.0,
    )


def _fetch_jepx_index(client: HttpClient) -> dict[str, float] | None:
    headers = {"Referer": "https://www.jepx.jp/"}
    year_text = client.get_text(
        "https://www.jepx.jp/js/get_graph_year.php?dir=spot_index",
        headers=headers,
    ).strip()
    if not year_text:
        return None
    latest_year = year_text.split(",")[0].strip()
    csv_text = client.get_text(
        f"https://www.jepx.jp/js/csv_read.php?dir=spot_index&file=spot_index_{quote(latest_year)}.csv",
        headers=headers,
    )
    rows = list(csv.reader(line for line in csv_text.splitlines() if line.strip()))
    if len(rows) < 2:
        return None
    latest = rows[-1]
    return {
        "date": latest[0],
        "da24": float(latest[1]),
        "dadt": float(latest[2]),
        "dapt": float(latest[3]),
        "ttv": float(latest[4]),
    }


def _fetch_occto_area_supply_demand(
    client: HttpClient,
    config: OfficialFreeConfig,
) -> dict[str, float] | None:
    target = config.briefing_date.strftime("%Y/%m/%d")
    data = client.get_json(
        f"https://web-kohyo.occto.or.jp/kks-web-public/home/dailyData?inputDate={quote(target)}"
    )
    if not isinstance(data, dict):
        return None
    areas = data.get("todayAreaRsvRateList") or []
    for area in areas:
        if area.get("areaCd") != config.occto_area_code:
            continue
        items = area.get("areaRsvRateItems") or []
        if not items:
            return None
        demands = [float(item["areaJyyu"]) for item in items if item.get("areaJyyu") is not None]
        reserve_rates = [float(item["areaRsvRate"]) for item in items if item.get("areaRsvRate") is not None]
        use_rates = [float(item["areaSyuRate"]) for item in items if item.get("areaSyuRate") is not None]
        return {
            "max_demand_gw": max(demands) / 1000.0,
            "min_reserve_rate": min(reserve_rates),
            "max_use_rate": max(use_rates),
        }
    return None


def _fetch_jma_weather(client: HttpClient, config: OfficialFreeConfig) -> dict[str, float | None] | None:
    data = client.get_json(
        f"https://www.jma.go.jp/bosai/forecast/data/forecast/{config.jma_prefecture_code}.json"
    )
    if not isinstance(data, list) or len(data) < 2:
        return None

    temp_target = config.jma_temp_area_name
    weekly_block = data[1]
    temp_series = weekly_block.get("timeSeries", [])
    if len(temp_series) < 2:
        return None

    forecast_temp_c: float | None = None
    normal_temp_c: float | None = None
    for area in temp_series[1].get("areas", []):
        if area.get("area", {}).get("name") != temp_target:
            continue
        temps_max = area.get("tempsMax") or []
        for value in temps_max:
            if value != "":
                forecast_temp_c = float(value)
                break
        break

    for area in weekly_block.get("tempAverage", {}).get("areas", []):
        if area.get("area", {}).get("name") == temp_target:
            normal_temp_c = float(area["max"])
            break

    if forecast_temp_c is None:
        first_block = data[0]
        time_series = first_block.get("timeSeries", [])
        if len(time_series) >= 3:
            for area in time_series[2].get("areas", []):
                if area.get("area", {}).get("name") != temp_target:
                    continue
                for value in reversed(area.get("temps", [])):
                    if value != "":
                        forecast_temp_c = float(value)
                        break
                break

    if forecast_temp_c is None:
        return None
    return {
        "forecast_temp_c": forecast_temp_c,
        "normal_temp_c": normal_temp_c,
    }


def _fetch_boj_usdjpy(client: HttpClient) -> float | None:
    page = client.get_text("https://www.boj.or.jp/en/statistics/market/forex/fxdaily/index.htm")
    if "fxlist/" not in page:
        return None
    return None


def _fetch_enecho_news(client: HttpClient) -> list[NewsEvent]:
    html = client.get_text("https://www.enecho.meti.go.jp/")
    items = _collect_tag_texts(html, {"a", "h3"})
    titles = _filter_titles(
        items,
        keywords=[
            "電力",
            "ガス",
            "エネルギー安全保障",
            "需給",
            "石油",
            "燃料",
            "再生可能エネルギー",
            "中東情勢",
        ],
    )
    events: list[NewsEvent] = []
    for title in titles[:6]:
        category, impact = _classify_official_headline(title)
        events.append(
            NewsEvent(
                headline=title,
                category=category,
                impact_direction=impact,
                confirmed=True,
                note="資源エネルギー庁",
            )
        )
    return events


def _fetch_nra_news(client: HttpClient) -> list[NewsEvent]:
    html = client.get_text("https://www.nra.go.jp/")
    items = _collect_tag_texts(html, {"a", "figcaption", "h3"})
    titles = _filter_titles(
        items,
        keywords=[
            "発電所",
            "原子炉",
            "規制検査",
            "事故",
            "トラブル",
            "泊",
            "川内",
            "柏崎刈羽",
            "浜岡",
            "島根",
        ],
    )
    events: list[NewsEvent] = []
    for title in titles[:6]:
        category, impact = _classify_nra_headline(title)
        events.append(
            NewsEvent(
                headline=title,
                category=category,
                impact_direction=impact,
                confirmed=True,
                note="原子力規制委員会",
            )
        )
    return events


def _collect_tag_texts(html: str, tags: set[str]) -> list[str]:
    parser = _TagTextParser(tags)
    parser.feed(html)
    return parser.items


def _filter_titles(items: list[str], keywords: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        text = re.sub(r"\s+", " ", item).strip()
        if len(text) < 6:
            continue
        if any(keyword in text for keyword in keywords):
            cleaned.append(text)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in cleaned:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _classify_official_headline(title: str) -> tuple[str, str]:
    if "中東情勢" in title or "石油" in title or "燃料" in title:
        return "fuel", "up"
    if "エネルギー安全保障" in title:
        return "fuel", "up"
    if "電気・ガス料金支援" in title or "値引き" in title:
        return "policy", "down"
    if "需給対策" in title or "電力" in title:
        return "policy", "uncertain"
    return "policy", "uncertain"


def _classify_nra_headline(title: str) -> tuple[str, str]:
    if "事故から" in title or "受賞" in title:
        return "supply", "uncertain"
    if "事故" in title or "トラブル" in title or "規制検査" in title:
        return "supply", "up"
    if "現地調査" in title or "関連審査会合" in title:
        return "supply", "uncertain"
    return "supply", "uncertain"
