"""Shared paths and helpers for the argus-param-i18n generators."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sources.json"
CACHE = ROOT / "cache"
OUT = ROOT / "out"
DIST = ROOT / "dist"

PACK_DIRS = ("meta", "tm", "glossary", "overrides")

# ArduPilot vehicle prefixes in pdef param names (contract: normalized to bare).
VEHICLE_PREFIXES = ("ArduCopter:", "ArduPlane:", "Rover:", "ArduSub:")
# Legacy (unversioned) directory names behind autotest.ardupilot.org/Parameters/.
LEGACY_XML_NAMES = {
    "Copter": "ArduCopter",
    "Plane": "ArduPlane",
    "Rover": "Rover",
    "Sub": "ArduSub",
}

LOCALES = ("zh", "en", "ja", "ko", "de", "fr", "es", "pt", "ru", "ar")

SERIES_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

USER_AGENT = "argus-param-i18n-generator/0.1 (+https://github.com/L-X-Yao/argus-param-i18n)"

# Largest pdef we accept (the real files are around 1-3 MB).
MAX_XML_BYTES = 64 * 1024 * 1024


def load_config() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def text_hash(text: str) -> str:
    """Contract: sha256 of the exact UTF-8 English text, lowercase hex, no normalization."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_canonical_int(value: float) -> bool:
    return isinstance(value, (int, float)) and float(value).is_integer()
