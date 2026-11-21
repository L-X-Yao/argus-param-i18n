"""Translate source.json strings into tm/<locale>.json.

Providers:
  claude-cli  batch-translate through the local Claude Code CLI (default);
  import      merge an existing JSON file (--file), hash- or English-keyed.

Usage:
  python -m tools.translate --locale zh --provider claude-cli [--limit N] [--batch N]
  python -m tools.translate --locale zh --provider import --file in.json

Every batch is validated (param names, numbers, placeholders, acronyms, length)
before it is written; a failing batch is retried, then split. The TM file is
rewritten atomically after every batch, so an interrupted run resumes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from .common import LOCALES, ROOT, read_json, text_hash, write_json

ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9_]{1,}\b")
PARAM_NAME_RE = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
ORDINAL_RE = re.compile(r"\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"%[sdf]|\{[a-zA-Z_][a-zA-Z0-9_]*\}")
WORD_NUMBER_RE = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|once)\b",
    re.IGNORECASE,
)
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
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "once": "1",
}
ORDINAL_WORD_RE = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth)",
    re.IGNORECASE,
)
ORDINAL_WORDS = {name: str(i) for i, name in enumerate(
    ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
     "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
     "eighteenth", "nineteenth", "twentieth"], 1)}
MULTIPLIER_WORDS = {
    "single": "1", "onewire": "1", "primary": "1",
    "double": "2", "twice": "2", "secondary": "2",
    "triple": "3", "thrice": "3", "tertiary": "3",
    "quadruple": "4", "quaternary": "4", "quintuple": "5", "sextuple": "6",
    "quadratic": "2", "cubic": "3",
}
MULTIPLIER_RE = re.compile(
    r"\b(single|onewire|primary|double|twice|secondary|triple|thrice|tertiary|quadruple|quaternary|quintuple|sextuple|quadratic|cubic)\b",
    re.IGNORECASE,
)
BASE_WORDS = {"binary": "2", "octal": "8", "decimal": "10", "hex": "16", "hexadecimal": "16"}
BASE_RE = re.compile(r"\b(binary|octal|decimal|hex|hexadecimal)\b", re.IGNORECASE)
IMPLICIT_ONE_RE = re.compile(r"\b(per|each|every)\b", re.IGNORECASE)
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

# Acronyms a translation must keep as-is (unless the glossary maps them, e.g.
# RTL -> 返航). Uppercase English words like NOTE or WARNING are not acronyms.
KEEP_ACRONYMS = {
    "GPS", "EKF", "IMU", "RC", "PID", "LED", "CAN", "SITL", "VTOL", "OSD",
    "AHRS", "RSSI", "RPM", "PPM", "PWM", "SBUS", "UAV", "GNSS", "RTK", "NMEA",
    "PDB", "BEC", "ESC", "UART", "I2C", "SPI", "LTM", "CRSF", "ELRS", "DSM",
    "SRXL", "FPORT", "MAVLink", "MAV", "BT", "WiFi", "LTE", "4G", "5G", "USB",
    "USD", "SD", "POSIX", "CRC", "VTX", "VCP", "FTP", "GCS",
}


def mandatory_numbers(text: str) -> list[str]:
    """Digits that must survive translation: every number except ordinals."""
    return sorted(NUM_RE.findall(ORDINAL_RE.sub(" ", text)))


def allowed_numbers(text: str) -> list[str]:
    """Digits the translation may contain: all of them, ordinals included
    ("4th" may legitimately become 第4, keeping the 4). An English number word
    may become a digit (zero -> 0)."""
    nums = NUM_RE.findall(text)
    nums.extend(WORD_NUMBERS[m.group(1).lower()] for m in WORD_NUMBER_RE.finditer(text))
    nums.extend(ORDINAL_WORDS[m.group(1).lower()] for m in ORDINAL_WORD_RE.finditer(text))
    nums.extend(MULTIPLIER_WORDS[m.group(1).lower()] for m in MULTIPLIER_RE.finditer(text))
    nums.extend(BASE_WORDS[m.group(1).lower()] for m in BASE_RE.finditer(text))
    if IMPLICIT_ONE_RE.search(text):
        nums.append("1")
    nums.extend(MONTH_NUMBERS[m.group(1).lower()] for m in MONTH_RE.finditer(text))
    return sorted(nums)


def load_glossary(locale: str) -> dict:
    path = ROOT / "glossary" / f"{locale}.json"
    return read_json(path) if path.exists() else {}


class Validator:
    def __init__(self, glossary: dict):
        # Glossary terms may replace an acronym entirely (RTL -> 返航).
        self.glossary = glossary

    def problems(self, src: str, dst: str) -> list[str]:
        if not dst or not dst.strip():
            return ["empty"]
        out = []
        # Every non-ordinal source number must survive; the translation may not
        # invent numbers, but ordinal digits may reappear (4th -> 第4).
        need = mandatory_numbers(src)
        have = mandatory_numbers(dst)
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
        src_ph = sorted(PLACEHOLDER_RE.findall(src))
        dst_ph = sorted(PLACEHOLDER_RE.findall(dst))
        if src_ph != dst_ph:
            out.append(f"placeholders {src_ph} -> {dst_ph}")
        for name in set(PARAM_NAME_RE.findall(src)):
            if name not in dst:
                out.append(f"param name {name} dropped")
        glossary_values = set(self.glossary.values())
        for acr in set(ACRONYM_RE.findall(src)):
            base = acr.rstrip("_")
            if base not in KEEP_ACRONYMS:
                continue  # NOTE/WARNING/ALL... are words, not acronyms
            if base in self.glossary or any(base in v for v in glossary_values if len(v) > len(base)):
                continue  # translated per glossary (e.g. RTL -> 返航)
            if base not in dst:
                out.append(f"acronym {acr} dropped")
        if len(dst) > max(3 * len(src), len(src) + 60):
            out.append("too long")
        return out


def build_prompt(batch: list[tuple[str, str]], locale: str, glossary: dict) -> str:
    lang = {"zh": "Simplified Chinese", "ja": "Japanese", "ko": "Korean", "de": "German",
            "fr": "French", "es": "Spanish", "pt": "Portuguese", "ru": "Russian",
            "ar": "Arabic", "en": "English"}[locale]
    terms = "\n".join(f'  "{k}" -> "{v}"' for k, v in sorted(glossary.items()))
    items = "\n".join(
        f"  {i}: {json.dumps(src, ensure_ascii=False)}" for i, (h, src) in enumerate(batch, 1)
    )
    return f"""You translate user-interface strings of an ArduPilot ground control station
into {lang}. The strings are parameter descriptions, short labels, and enumeration
values from ArduPilot's parameter metadata.

Rules, in order of importance:
1. Keep every parameter name (ALL_CAPS_WITH_UNDERSCORES), number, unit (cm, m/s,
   degrees, %, us), and placeholder (%s, {{name}}) EXACTLY as in the source.
   Write numbers as digits, never as words (2, not "two"/"zwei"/"اثنان").
2. Keep acronyms like GPS, EKF, IMU, RC, PID, LED, CAN, MAVLink, SITL, VTOL
   untranslated, unless the glossary maps them.
3. Follow the glossary strictly for consistency.
4. Technical register, concise. Do not add explanation, quotes or trailing
   punctuation that the source does not have.

Glossary:
{terms}

Translate each numbered string. Answer with ONE JSON object mapping the number to
the translation, and NOTHING else (no markdown fence). Example: {{"1": "..."}}

Strings:
{items}"""


MODEL = "claude-haiku-5-5"  # machine first pass; --model overrides


def call_claude(prompt: str, timeout: float = 600.0) -> str:
    # Machine first pass on a fast tier; the glossary plus the validator keep
    # quality acceptable, and review (r=1) is a human step anyway.
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", MODEL, "--output-format", "json"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed ({proc.returncode}): {proc.stderr[:400]}")
    wrapper = json.loads(proc.stdout)
    return wrapper.get("result", "")


def parse_reply(reply: str, count: int) -> dict[int, str]:
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in reply")
    data = json.loads(text[start : end + 1])
    out = {}
    for k, v in data.items():
        try:
            idx = int(k)
        except (TypeError, ValueError):
            continue
        if isinstance(v, str):
            out[idx] = v
    if len(out) < count // 2:
        raise ValueError(f"reply covers {len(out)}/{count}")
    return out


def translate_batch(batch: list[tuple[str, str]], locale: str, glossary: dict,
                    validator: Validator) -> dict[str, str]:
    """Returns hash -> translation for the strings that validated."""
    prompt = build_prompt(batch, locale, glossary)
    reply = call_claude(prompt)
    parsed = parse_reply(reply, len(batch))
    accepted: dict[str, str] = {}
    for i, (h, src) in enumerate(batch, 1):
        dst = parsed.get(i)
        if dst is None:
            continue
        problems = validator.problems(src, dst)
        if not problems:
            accepted[h] = dst.strip()
    return accepted


def run_claude_cli(locale: str, limit: int | None, batch_size: int, workers: int = 1) -> int:
    from concurrent.futures import ThreadPoolExecutor

    source = read_json(ROOT / "source.json")
    tm_path = ROOT / "tm" / f"{locale}.json"
    tm = read_json(tm_path) if tm_path.exists() else {}
    generated = read_json(ROOT / "generated.json") if (ROOT / "generated.json").exists() else {}
    glossary = load_glossary(locale)
    validator = Validator(glossary)

    todo = [(h, s) for h, s in sorted(source.items()) if h not in tm or not tm[h].get("t")]
    if limit:
        todo = todo[:limit]
    print(f"{locale}: {len(todo)} strings to translate ({len(tm)} already present)")

    batches = [todo[start : start + batch_size] for start in range(0, len(todo), batch_size)]
    failures: list[str] = []
    done = 0

    def run_batch(batch):
        accepted = {}
        try:
            accepted = translate_batch(batch, locale, glossary, validator)
        except (RuntimeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            print(f"batch failed ({len(batch)} strings): {exc}", file=sys.stderr)
        missing = [(h, s) for h, s in batch if h not in accepted]
        # Cap solo retries: a fully failed large batch must not turn into
        # len(batch) sequential calls holding a worker for an hour.
        for h, src in missing[:5]:
            try:
                accepted.update(translate_batch([(h, src)], locale, glossary, validator))
            except (RuntimeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
                pass
        return accepted, [h for h, _ in batch if h not in accepted]

    from concurrent.futures import as_completed

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_batch, b) for b in batches]
        for i, fut in enumerate(as_completed(futures), 1):
            accepted, failed = fut.result()
            for h, dst in accepted.items():
                entry: dict = {"t": dst, "r": 0}
                if h in generated:
                    entry["s"] = "generated"
                tm[h] = entry
                done += 1
            failures.extend(failed)
            write_json(tm_path, tm)  # checkpoint after every completed batch
            print(f"  batch {i}/{len(batches)}: +{len(accepted)}, {len(failures)} failed so far")

    if failures:
        (ROOT / "out").mkdir(exist_ok=True)
        (ROOT / "out" / f"translate_failures_{locale}.txt").write_text(
            "\n".join(f"{h}\t{source[h]}" for h in failures), encoding="utf-8")
        print(f"{locale}: {len(failures)} failures written to out/translate_failures_{locale}.txt")
    print(f"{locale}: +{done} translations, tm now {len(tm)} entries")
    return 0 if not failures else 2


def run_import(locale: str, file: Path) -> int:
    source = read_json(ROOT / "source.json")
    tm_path = ROOT / "tm" / f"{locale}.json"
    tm = read_json(tm_path) if tm_path.exists() else {}
    data = read_json(file)
    n = 0
    for key, val in data.items():
        h = key if re.fullmatch(r"[0-9a-f]{64}", key) else text_hash(key)
        if h not in source:
            print(f"skip (unknown source): {key[:60]}", file=sys.stderr)
            continue
        if isinstance(val, str):
            entry = {"t": val, "r": 0}
        elif isinstance(val, dict) and isinstance(val.get("t"), str):
            entry = {"t": val["t"], "r": 1 if val.get("r") == 1 else 0}
        else:
            print(f"skip (bad value): {key[:60]}", file=sys.stderr)
            continue
        if h in tm and tm[h].get("r") == 1 and entry["r"] == 0:
            continue  # never downgrade a reviewed entry
        tm[h] = entry
        n += 1
    write_json(tm_path, tm)
    print(f"{locale}: imported {n} entries, tm now {len(tm)}")
    return 0


def main() -> int:
    global MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale", required=True, choices=LOCALES)
    ap.add_argument("--provider", default="claude-cli", choices=("claude-cli", "import"))
    ap.add_argument("--file", type=Path, help="JSON file for --provider import")
    ap.add_argument("--limit", type=int, help="translate only the first N untranslated strings")
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--workers", type=int, default=1, help="parallel claude -p calls")
    ap.add_argument("--model", default=MODEL, help="model for claude -p (default: fast tier)")
    args = ap.parse_args()
    MODEL = args.model
    if args.provider == "import":
        if not args.file:
            ap.error("--file is required with --provider import")
        return run_import(args.locale, args.file)
    return run_claude_cli(args.locale, args.limit, args.batch, args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
