from __future__ import annotations

import unittest

from newsforprediction.analysis import build_briefing
from newsforprediction.loader import load_input_payload
from newsforprediction.rendering import render_markdown


class MorningBriefingTests(unittest.TestCase):
    def test_briefing_classifies_pressures_and_pending_items(self) -> None:
        payload = load_input_payload(
            {
                "briefing_date": "2026-06-15",
                "metrics": [
                    {
                        "name": "JKM",
                        "category": "fuel",
                        "current": 13.0,
                        "previous": 12.0,
                        "week_ago": 11.0,
                        "unit": "USD/MMBtu",
                        "higher_means": "up",
                        "abnormal_daily_pct_threshold": 4.0
                    },
                    {
                        "name": "USD/JPY",
                        "category": "fx",
                        "current": 158.0,
                        "previous": 156.0,
                        "week_ago": 154.0,
                        "unit": "JPY",
                        "higher_means": "up",
                        "abnormal_daily_pct_threshold": 0.7
                    }
                ],
                "weather": {
                    "region": "Tokyo",
                    "forecast_temp_c": 31.0,
                    "previous_forecast_temp_c": 28.5,
                    "normal_temp_c": 27.0,
                    "sensitivity_mode": "cooling"
                },
                "demand": {
                    "forecast_gw": 95.0,
                    "previous_forecast_gw": 90.0,
                    "week_ago_forecast_gw": 88.0
                },
                "plant_events": [
                    {
                        "plant_name": "Plant A",
                        "status": "stop",
                        "confirmed": True
                    },
                    {
                        "plant_name": "Plant B",
                        "status": "restart",
                        "confirmed": False
                    }
                ],
                "news_events": [
                    {
                        "headline": "Geopolitical tension",
                        "category": "geopolitics",
                        "impact_direction": "up",
                        "confirmed": True
                    }
                ]
            }
        )

        result = build_briefing(payload)

        self.assertEqual(result.summary.fuel, "up")
        self.assertEqual(result.summary.fx, "up")
        self.assertEqual(result.summary.weather_demand, "up")
        self.assertEqual(result.summary.supply, "unconfirmed")
        self.assertTrue(any("未確認" in item or "評価保留" in item for item in result.pending_items))

    def test_markdown_matches_requested_sections(self) -> None:
        payload = load_input_payload(
            {
                "briefing_date": "2026-06-15",
                "metrics": [
                    {
                        "name": "JEPX",
                        "category": "power",
                        "current": 15.0,
                        "previous": 12.0,
                        "week_ago": 10.0,
                        "unit": "JPY/kWh",
                        "higher_means": "up",
                        "abnormal_daily_pct_threshold": 8.0
                    }
                ],
                "weather": {
                    "region": "Tokyo",
                    "forecast_temp_c": 29.0,
                    "previous_forecast_temp_c": 29.0,
                    "normal_temp_c": 28.0,
                    "sensitivity_mode": "cooling"
                },
                "demand": {
                    "forecast_gw": 90.0,
                    "previous_forecast_gw": 90.0,
                    "week_ago_forecast_gw": 89.0
                },
                "plant_events": [],
                "news_events": [],
                "used_sources": ["JEPX"],
                "checked_but_unused_sources": ["BOJ"]
            }
        )

        markdown = render_markdown(build_briefing(payload))

        self.assertIn("# 朝会ブリーフィング 2026-06-15", markdown)
        self.assertIn("## 1. 今日の要約", markdown)
        self.assertIn("## 2. 前日から大きく動いた指標", markdown)
        self.assertIn("## 3. 予測値が外れそうな理由候補", markdown)
        self.assertIn("## 4. 今日見るべきデータ", markdown)
        self.assertIn("## 5. 判断保留すべき点", markdown)
        self.assertIn("## 6. 参照ソース", markdown)
        self.assertIn("JEPX", markdown)
        self.assertIn("BOJ", markdown)
        self.assertIn("| JEPX |", markdown)

    def test_missing_reference_values_are_reported_as_pending(self) -> None:
        payload = load_input_payload(
            {
                "briefing_date": "2026-06-15",
                "metrics": [
                    {
                        "name": "Brent",
                        "category": "fuel",
                        "current": 81.0,
                        "unit": "USD/bbl",
                        "higher_means": "up"
                    }
                ],
                "plant_events": [],
                "news_events": []
            }
        )

        result = build_briefing(payload)

        self.assertTrue(any("Brent" in item for item in result.pending_items))


if __name__ == "__main__":
    unittest.main()
