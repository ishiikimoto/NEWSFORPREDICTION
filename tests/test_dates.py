from __future__ import annotations

import unittest
from unittest.mock import patch

from newsforprediction.live import _load_config
from newsforprediction.loader import load_input_payload


class DateDefaultTests(unittest.TestCase):
    def test_regular_input_defaults_to_today_in_tokyo(self) -> None:
        with patch("newsforprediction.loader.today_in_tokyo", return_value=_date("2026-06-16")):
            payload = load_input_payload({"metrics": []})
        self.assertEqual(payload.briefing_date.isoformat(), "2026-06-16")

    def test_official_free_config_defaults_to_today_in_tokyo(self) -> None:
        from pathlib import Path
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "region_name": "Tokyo",
                        "jma_prefecture_code": "130000",
                        "jma_temp_area_name": "東京",
                        "occto_area_code": "03",
                        "occto_area_name": "東京",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch("newsforprediction.live.today_in_tokyo", return_value=_date("2026-06-16")):
                config = _load_config(str(path))
        self.assertEqual(config.briefing_date.isoformat(), "2026-06-16")


def _date(value: str):
    from datetime import date

    return date.fromisoformat(value)


if __name__ == "__main__":
    unittest.main()
