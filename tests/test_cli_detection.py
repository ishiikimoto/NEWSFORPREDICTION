from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from main import _looks_like_official_free_config


class CliDetectionTests(unittest.TestCase):
    def test_detects_official_free_config_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "briefing_date": "2026-06-15",
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
            self.assertTrue(_looks_like_official_free_config(str(path)))

    def test_regular_input_is_not_treated_as_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "input.json"
            path.write_text(
                json.dumps(
                    {
                        "briefing_date": "2026-06-15",
                        "metrics": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.assertFalse(_looks_like_official_free_config(str(path)))


if __name__ == "__main__":
    unittest.main()
