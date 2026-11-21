"""Validate the working tree against the PARAM_I18N contract.

Usage: python -m tools.validate [--locale zh] [--strict]

Errors (exit 1): broken schema, hash mismatch, placeholder/number/name loss,
manifest numbers that do not match the data, pack file shape.
Warnings: length outliers, empty locale files, TM entries whose hash is not in
source.json (kept for provenance across versions; --strict makes them errors).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .common import (
    LOCALES,
    OUT,
    ROOT,
    SERIES_RE,
    VEHICLE_PREFIXES,
    load_config,
    read_json,
    text_hash,
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
ORDINAL_RE = re.compile(r"\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
PARAM_NAME_RE = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b")
PLACEHOLDER_RE = re.compile(r"%[sdf]|\{[a-zA-Z_][a-zA-Z0-9_]*\}")
WORD_NUMBER_RE = re.compile(r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten)\b", re.IGNORECASE)
WORD_NUMBERS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
    re.IGNORECASE,
)
MONTH_NUMBERS = {
    "january": "1",
    "february": "2",
    "march": "3",
    "april": "4",
    "may": "5",
    "june": "6",
    "july": "7",
    "august": "8",
    "september": "9",
    "october": "10",
    "november": "11",
    "december": "12",
}


def mandatory_numbers(text: str) -> list[str]:
    """Digits that must survive translation: every number except ordinals."""
    return sorted(NUM_RE.findall(ORDINAL_RE.sub(" ", text)))


def allowed_numbers(text: str) -> list[str]:
    """Digits the translation may contain: all source numbers, ordinals included.

    An English number word may legitimately become a digit (zero -> 0), so its
    value is allowed as well. The reverse is not required.
    """
    nums = NUM_RE.findall(text)
    nums.extend(WORD_NUMBERS[m.group(1).lower()] for m in WORD_NUMBER_RE.finditer(text))
    nums.extend(MONTH_NUMBERS[m.group(1).lower()] for m in MONTH_RE.finditer(text))
    return sorted(nums)


def number_problems(src: str, dst: str) -> list[str]:
    out = []
    need, have = mandatory_numbers(src), mandatory_numbers(dst)
    for n in need:
        if n in have:
            have.remove(n)
        else:
            out.append(f"number {n} dropped")
    allowed = allowed_numbers(src)
    for n in NUM_RE.findall(dst):
        if n in allowed:
            allowed.remove(n)
        else:
            out.append(f"number {n} invented")
    return out


def check(condition: bool, errors: list, msg: str) -> bool:
    if not condition:
        errors.append(msg)
    return condition


def validate_meta(errors: list, warnings: list) -> None:
    cfg = load_config()
    for vehicle, vcfg in sorted(cfg["vehicles"].items()):
        for series in vcfg["series"]:
            path = ROOT / "meta" / vehicle / f"{series}.json"
            if not check(path.exists(), errors, f"missing {path}"):
                continue
            meta = read_json(path)
            for name, entry in meta.items():
                if ":" in name:
                    errors.append(f"{vehicle}/{series}: unstripped prefix in {name}")
                if not isinstance(entry, dict):
                    errors.append(f"{vehicle}/{series} {name}: entry not an object")
                    continue
                for field in ("desc", "human"):
                    if not isinstance(entry.get(field, ""), str):
                        errors.append(f"{vehicle}/{series} {name}: {field} not a string")
                rng = entry.get("range")
                if rng is not None and not (isinstance(rng, list) and len(rng) == 2):
                    errors.append(f"{vehicle}/{series} {name}: bad range {rng}")
                for field in ("values", "bitmask"):
                    v = entry.get(field)
                    if v is not None and not isinstance(v, dict):
                        errors.append(f"{vehicle}/{series} {name}: {field} not an object")
                for field in ("step", "default"):
                    v = entry.get(field)
                    if v is not None and not isinstance(v, (int, float)):
                        errors.append(f"{vehicle}/{series} {name}: {field} not numeric")
            print(f"meta {vehicle}/{series}: {len(meta)} params ok-shape")


def validate_tm(locale: str, source: dict, generated: dict, errors: list, warnings: list,
                strict: bool) -> None:
    tm_path = ROOT / "tm" / f"{locale}.json"
    if not tm_path.exists():
        warnings.append(f"tm/{locale}.json does not exist")
        return
    tm = read_json(tm_path)
    for h, entry in tm.items():
        if not HEX64.match(h):
            errors.append(f"tm/{locale}: key not sha256 hex: {h[:20]}")
            continue
        if h not in source:
            msg = f"tm/{locale}: hash not in source.json: {h[:12]} ({entry.get('t', '')[:30]})"
            (errors if strict else warnings).append(msg)
            continue
        if entry.get("t") != source[h] and not isinstance(entry.get("t"), str):
            errors.append(f"tm/{locale} {h[:12]}: t missing")
            continue
        if not str(entry.get("t", "")).strip():
            errors.append(f"tm/{locale} {h[:12]}: empty translation")
            continue
        if entry.get("r") not in (0, 1):
            errors.append(f"tm/{locale} {h[:12]}: r not 0/1")
        if entry.get("s") is not None and entry.get("s") != "generated":
            errors.append(f"tm/{locale} {h[:12]}: unknown s {entry.get('s')}")
        if entry.get("s") == "generated" and h not in generated:
            warnings.append(f"tm/{locale} {h[:12]}: s=generated but hash not in generated.json")
        src = source[h]
        dst = str(entry["t"])
        nproblems = number_problems(src, dst)
        if nproblems:
            errors.append(f"tm/{locale} {h[:12]}: {nproblems}: {src[:50]!r} -> {dst[:50]!r}")
        if sorted(PLACEHOLDER_RE.findall(src)) != sorted(PLACEHOLDER_RE.findall(dst)):
            errors.append(f"tm/{locale} {h[:12]}: placeholders changed: {src[:50]!r}")
        for name in set(PARAM_NAME_RE.findall(src)):
            if name not in dst:
                errors.append(f"tm/{locale} {h[:12]}: param name {name} dropped")
        if len(dst) > max(3 * len(src), len(src) + 60):
            warnings.append(f"tm/{locale} {h[:12]}: suspiciously long: {dst[:60]!r}")
    print(f"tm/{locale}: {len(tm)} entries checked")


def validate_manifest(errors: list, warnings: list) -> dict:
    path = ROOT / "manifest.json"
    if not check(path.exists(), errors, "missing manifest.json"):
        return {}
    m = read_json(path)
    check(m.get("schema") == 1, errors, "manifest schema != 1")
    check(m.get("license") == "GPL-3.0", errors, "manifest license != GPL-3.0")
    check(isinstance(m.get("min_argus"), str), errors, "manifest min_argus missing")
    check(re.match(r"^\d+\.\d+\.\d+$", str(m.get("min_argus", ""))) is not None,
          errors, "manifest min_argus not x.y.z")
    if m.get("data_version") == "unreleased":
        warnings.append("manifest data_version is the pre-release placeholder; run tools.release before publishing")
    else:
        check(re.match(r"^\d{4}\.\d{2}\.\d+$", str(m.get("data_version", ""))) is not None,
              errors, "manifest data_version not YYYY.MM.N")
    source = read_json(ROOT / "source.json") if (ROOT / "source.json").exists() else {}
    cfg = load_config()
    expected = {(v, s) for v, c in cfg["vehicles"].items() for s in c["series"]}
    got = {(s.get("vehicle"), s.get("series")) for s in m.get("sources", [])}
    check(expected == got, errors, f"manifest sources {sorted(got)} != config {sorted(expected)}")
    for s in m.get("sources", []):
        check(bool(s.get("url")), errors, f"manifest source {s.get('vehicle')} missing url")
        check(bool(s.get("sha256")) and HEX64.match(str(s.get("sha256", ""))) is not None,
              errors, f"manifest source {s.get('vehicle')}/{s.get('series')} bad sha256")
        check(isinstance(s.get("params"), int) and s.get("params", 0) > 0,
              errors, f"manifest source {s.get('vehicle')}/{s.get('series')} bad params count")
        meta_path = ROOT / "meta" / str(s.get("vehicle")) / f"{s.get('series')}.json"
        if meta_path.exists():
            actual = len(read_json(meta_path))
            check(actual == s.get("params"), errors,
                  f"manifest params {s.get('vehicle')}/{s.get('series')}={s.get('params')} != meta {actual}")
    for locale, stats in m.get("locales", {}).items():
        check(locale in LOCALES, errors, f"manifest locale {locale} not in whitelist")
        tm_path = ROOT / "tm" / f"{locale}.json"
        tm = read_json(tm_path) if tm_path.exists() else {}
        check(stats.get("total") == len(source), errors,
              f"manifest {locale}.total={stats.get('total')} != source.json {len(source)}")
        check(stats.get("translated") == len(tm), errors,
              f"manifest {locale}.translated={stats.get('translated')} != tm {len(tm)}")
        check(stats.get("reviewed") == sum(1 for v in tm.values() if v.get("r") == 1), errors,
              f"manifest {locale}.reviewed wrong")
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale", choices=LOCALES)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    validate_meta(errors, warnings)
    source = read_json(ROOT / "source.json") if (ROOT / "source.json").exists() else {}
    generated = read_json(ROOT / "generated.json") if (ROOT / "generated.json").exists() else {}
    check(bool(source), errors, "source.json empty or missing")
    for h, s in source.items():
        if not HEX64.match(h) or text_hash(s) != h:
            errors.append(f"source.json hash mismatch: {h[:12]}")
            break
    aliases_path = ROOT / "aliases.json"
    if aliases_path.exists():
        aliases = read_json(aliases_path)
        for vehicle, mapping in aliases.items():
            for old, new in mapping.items():
                if any(p in old for p in VEHICLE_PREFIXES):
                    errors.append(f"aliases {vehicle}: prefixed name {old}")
    if args.locale:
        validate_tm(args.locale, source, generated, errors, warnings, args.strict)

    validate_manifest(errors, warnings)

    OUT.mkdir(exist_ok=True)
    (OUT / "validation.txt").write_text(
        "\n".join(["ERRORS:"] + [f"  {e}" for e in errors] + ["WARNINGS:"] + [f"  {w}" for w in warnings]) + "\n",
        encoding="utf-8")
    for e in errors[:30]:
        print(f"ERROR {e}", file=sys.stderr)
    for w in warnings[:30]:
        print(f"warn  {w}")
    print(f"{len(errors)} errors, {len(warnings)} warnings -> out/validation.txt")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
