"""Build glossary/<locale>.json from the English term keys in glossary/zh.json.

Usage: python -m tools.build_glossary --locale ja [--model claude-haiku-5-5]

The glossary is a consistency constraint for tools.translate, not a native
review. Technical acronyms below are kept identical on purpose; every other
term is translated by the model and checked for the exact key set.
"""

from __future__ import annotations

import argparse
import json

from . import translate
from .common import LOCALES, ROOT, read_json, write_json

LANG = {
    "zh": "Simplified Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "en": "English",
}
KEEP = {"ESC", "GCS", "IMU", "EKF", "GPS", "RPM", "VTOL", "CAN", "DroneCAN"}


def build_prompt(keys: list[str], locale: str) -> str:
    terms = json.dumps(keys, ensure_ascii=False)
    return f"""You maintain a terminology glossary for {LANG[locale]} translations of
ArduPilot ground-control-station parameter descriptions.

Translate every English term below into {LANG[locale]}. Use the concise form a
pilot or engineer would see in the UI. Keep these technical acronyms EXACTLY as
written: {", ".join(sorted(KEEP))}. Do not add explanations, punctuation or
line breaks.

Return ONE JSON object mapping every input key exactly to its translation and
nothing else (no markdown fence).

Terms:
{terms}"""


def parse_reply(reply: str) -> dict[str, str]:
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in reply")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("reply is not an object")
    return {str(k): str(v) for k, v in data.items()}


def validate_glossary(data: dict[str, str], keys: list[str]) -> list[str]:
    errors: list[str] = []
    if set(data) != set(keys):
        errors.append(f"keys differ: missing={sorted(set(keys) - set(data))} extra={sorted(set(data) - set(keys))}")
    for key in keys:
        value = data.get(key, "")
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key}: empty")
        elif "\n" in value:
            errors.append(f"{key}: line break")
        elif key in KEEP and value != key:
            errors.append(f"{key}: acronym changed to {value!r}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale", required=True, choices=LOCALES)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.locale == "zh":
        raise SystemExit("zh glossary is authored; edit glossary/zh.json directly")
    path = ROOT / "glossary" / f"{args.locale}.json"
    if path.exists() and not args.force:
        raise SystemExit(f"{path} exists; pass --force to replace it")
    keys = list(read_json(ROOT / "glossary" / "zh.json"))
    translate.MODEL = args.model
    reply = translate.call_claude(build_prompt(keys, args.locale))
    data = parse_reply(reply)
    errors = validate_glossary(data, keys)
    if errors:
        raise SystemExit("\n".join(errors))
    write_json(path, data)
    print(f"{args.locale}: {len(data)} terms -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
