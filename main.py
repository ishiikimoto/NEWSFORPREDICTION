from __future__ import annotations

import argparse
import json
from pathlib import Path

from newsforprediction.analysis import build_briefing
from newsforprediction.live import build_official_free_input
from newsforprediction.loader import load_input_file
from newsforprediction.rendering import render_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a morning briefing for power and fuel price prediction."
    )
    parser.add_argument("--input", help="Path to the JSON input file.")
    parser.add_argument(
        "--official-free-config",
        help="Path to the official free-source config JSON.",
    )
    parser.add_argument("--output", help="Optional output path for the rendered markdown.")
    return parser.parse_args()


def _looks_like_official_free_config(path: str) -> bool:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    required_keys = {
        "region_name",
        "jma_prefecture_code",
        "jma_temp_area_name",
        "occto_area_code",
        "occto_area_name",
    }
    return required_keys.issubset(payload.keys()) and "metrics" not in payload


def main() -> None:
    args = parse_args()
    if not args.input and not args.official_free_config:
        raise SystemExit("Either --input or --official-free-config is required.")

    if args.official_free_config:
        payload = build_official_free_input(args.official_free_config)
    elif args.input and _looks_like_official_free_config(args.input):
        payload = build_official_free_input(args.input)
    else:
        payload = load_input_file(args.input)
    briefing = build_briefing(payload)
    markdown = render_markdown(briefing)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
