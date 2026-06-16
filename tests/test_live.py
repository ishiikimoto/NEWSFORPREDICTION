from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from newsforprediction.history import HistoryStore
from newsforprediction.live import (
    _classify_nra_headline,
    _classify_official_headline,
    _collect_tag_texts,
    _extract_eia_brent_value,
    _filter_titles,
    _metric_from_history,
    _midpoint_from_range,
    _select_boj_pdf_url,
)
from newsforprediction.models import MetricInput


class LiveSourceTests(unittest.TestCase):
    def test_history_backfills_previous_and_week_ago(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            history = HistoryStore.load(Path(tmpdir) / "history.json")
            history.record_value("metrics", "JEPX DA-24", _date("2026-06-07"), 10.0)
            history.record_value("metrics", "JEPX DA-24", _date("2026-06-14"), 12.0)

            metric = _metric_from_history(
                history=history,
                bucket="metrics",
                target_date=_date("2026-06-15"),
                key="JEPX DA-24",
                metric=MetricInput(
                    name="JEPX DA-24",
                    category="power",
                    current=14.0,
                    higher_means="up",
                ),
            )

            self.assertEqual(metric.previous, 12.0)
            self.assertEqual(metric.week_ago, 10.0)

    def test_html_text_collection_and_keyword_filtering(self) -> None:
        html = """
        <html><body>
        <a href="/a">2026年度夏季の電力需給対策を取りまとめました</a>
        <figcaption>泊発電所の現地調査</figcaption>
        <a href="/b">関係ない短文</a>
        </body></html>
        """

        texts = _collect_tag_texts(html, {"a", "figcaption"})
        filtered = _filter_titles(texts, ["電力", "発電所"])

        self.assertIn("2026年度夏季の電力需給対策を取りまとめました", filtered)
        self.assertIn("泊発電所の現地調査", filtered)

    def test_headline_classification(self) -> None:
        self.assertEqual(
            _classify_official_headline("中東情勢を踏まえた石油及び関連製品等に関する対応"),
            ("fuel", "up"),
        )
        self.assertEqual(
            _classify_nra_headline("中部電力本店での原子力規制検査"),
            ("supply", "up"),
        )

    def test_select_boj_pdf_url_uses_latest_release_not_after_target(self) -> None:
        page = """
        <a href="/en/statistics/market/forex/fxdaily/fxlist/fx260616.pdf">June 16</a>
        <a href="/en/statistics/market/forex/fxdaily/fxlist/fx260615.pdf">June 15</a>
        <a href="/en/statistics/market/forex/fxdaily/fxlist/fx260612.pdf">June 12</a>
        """

        url = _select_boj_pdf_url(page, _date("2026-06-15"))

        self.assertEqual(
            url,
            "https://www.boj.or.jp/en/statistics/market/forex/fxdaily/fxlist/fx260615.pdf",
        )

    def test_midpoint_from_range_parses_boj_quote(self) -> None:
        self.assertEqual(_midpoint_from_range("160.22-24"), 160.23)

    def test_extract_eia_brent_value_uses_latest_business_day(self) -> None:
        html = """
        <td class='B6'>&nbsp;&nbsp;2026 Jun- 1 to Jun- 5</td>
        <td class='B3'>98.29</td>
        <td class='B3'>98.49</td>
        <td class='B3'>101.69</td>
        <td class='B3'>98.98</td>
        <td class='B3'>97.29</td>
        </tr>
        <tr>
        <td class='B6'>&nbsp;&nbsp;2026 Jun- 8 to Jun-12</td>
        <td class='B3'>97.46</td>
        <td class='B3'></td>
        <td class='B3'></td>
        <td class='B3'></td>
        <td class='B3'></td>
        </tr>
        """

        self.assertEqual(_extract_eia_brent_value(html, _date("2026-06-08")), 97.46)
        self.assertEqual(_extract_eia_brent_value(html, _date("2026-06-05")), 97.29)


def _date(value: str):
    from datetime import date

    return date.fromisoformat(value)


if __name__ == "__main__":
    unittest.main()
