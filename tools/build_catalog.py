"""Normalize cached pdef XML into meta/, source.json, aliases.json and the manifest.

Usage: python -m tools.build_catalog [--vehicle-params FILE]

Field parsing mirrors Argus backend/param_meta.py:_parse_xml (the pack must carry
the same fields the runtime expects). Vehicle prefixes (ArduCopter: etc.) are
stripped; when a bare and a prefixed form both exist the bare form wins and the
collision is reported. overrides/<vehicle>.json is authored by hand; this step
only reads it, folds its English text into source.json and records which hashes
are generated (drives tm "s": "generated").
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .common import (
    CACHE,
    OUT,
    ROOT,
    SERIES_RE,
    VEHICLE_PREFIXES,
    file_sha256,
    is_canonical_int,
    load_config,
    text_hash,
    write_json,
)

GENERIC_FIELDS = ("desc", "human")


def parse_pdef(raw: bytes) -> dict:
    """Same field extraction as backend/param_meta.py:_parse_xml (desc/human/group
    from attributes; Range/Units/Increment/Default/Bitmask fields; value codes)."""
    root = ET.fromstring(raw)
    meta: dict = {}
    for group in root.iter("parameters"):
        gname = group.get("name", "")
        for param in group.iter("param"):
            name = param.get("name", "")
            if not name:
                continue
            entry: dict = {
                "desc": param.get("documentation", ""),
                "human": param.get("humanName", ""),
                "group": gname,
            }
            for field in param.iter("field"):
                fn = field.get("name", "")
                ft = (field.text or "").strip()
                if fn == "Range":
                    parts = ft.split()
                    if len(parts) == 2:
                        try:
                            entry["range"] = [float(parts[0]), float(parts[1])]
                        except ValueError:
                            pass
                elif fn == "Units":
                    entry["units"] = ft
                elif fn == "Increment":
                    try:
                        entry["step"] = float(ft)
                    except ValueError:
                        pass
                elif fn == "Default":
                    try:
                        entry["default"] = float(ft)
                    except ValueError:
                        pass
                elif fn == "Bitmask":
                    bits = {}
                    for item in ft.split(","):
                        item = item.strip()
                        if ":" in item:
                            k, v = item.split(":", 1)
                            bits[k.strip()] = v.strip()
                    if bits:
                        entry["bitmask"] = bits
            values = {}
            for val in param.iter("value"):
                code = val.get("code", "")
                if code:
                    values[code] = val.text or ""
            if values:
                entry["values"] = values
            meta[name] = entry
    return meta


def _canonical(entry: dict) -> dict:
    """Integral floats to ints (fixture style: 1500, not 1500.0)."""
    for key in ("step", "default"):
        if key in entry and is_canonical_int(entry[key]):
            entry[key] = int(entry[key])
    if "range" in entry and all(is_canonical_int(v) for v in entry["range"]):
        entry["range"] = [int(v) for v in entry["range"]]
    return entry


def normalize(raw: bytes, warnings: list) -> dict:
    """Strip vehicle prefixes. When both a prefixed and a bare form exist the bare
    form wins (contract); any collision with differing content is reported."""
    parsed = parse_pdef(raw)
    out: dict = {}
    bare_origin: dict = {}  # bare name -> True when stored under its own bare form
    for name, entry in parsed.items():  # document order, like _parse_xml
        bare = name
        for prefix in VEHICLE_PREFIXES:
            if name.startswith(prefix):
                bare = name[len(prefix):]
                break
        is_bare = bare == name
        if bare not in out:
            out[bare] = _canonical(dict(entry))
            bare_origin[bare] = is_bare
            continue
        if out[bare] == entry:
            continue  # identical duplicate
        if bare_origin[bare]:
            warnings.append(f"{bare}: bare form kept, {name} differs")  # bare wins
        elif is_bare:
            warnings.append(f"{bare}: bare form replaces {name}")
            out[bare] = _canonical(dict(entry))  # bare wins over an earlier prefixed form
            bare_origin[bare] = True
        else:
            warnings.append(f"{bare}: first prefixed form kept, {name} differs")
    return out


def collect_texts(meta: dict, override_meta: dict | None = None) -> list[str]:
    texts: list[str] = []
    for entry in meta.values():
        for field in GENERIC_FIELDS:
            v = entry.get(field, "")
            if v:
                texts.append(v)
        for key in ("values", "bitmask"):
            for label in entry.get(key, {}).values():
                if label:
                    texts.append(label)
    for entry in (override_meta or {}).values():
        for field in GENERIC_FIELDS:
            v = entry.get(field, "")
            if v:
                texts.append(v)
    return texts


def derive_aliases(series_meta: dict, report: list) -> dict:
    """Rename candidates between consecutive series, for the coverage report only.

    A fingerprint match (identical human + desc + default + units) is NOT proof of
    a rename: ArduPilot documents sibling parameters (CAM_* vs CAM2_*, TRQ_* vs
    TRQ2_*, EK2_* vs EK3_*) with byte-identical text, and a wrong alias shows one
    parameter another parameter's metadata. aliases.json is therefore authored by
    hand; the machine candidates stay here for a human to confirm."""
    names = sorted(series_meta)
    candidates: dict = {}
    for older, newer in zip(names, names[1:]):
        old_meta, new_meta = series_meta[older], series_meta[newer]
        fingerprint_new = {
            (e.get("human", ""), e.get("desc", ""), e.get("default"), e.get("units", "")): n
            for n, e in new_meta.items()
        }
        missing = sorted(set(old_meta) - set(new_meta))
        for name in missing:
            e = old_meta[name]
            fp = (e.get("human", ""), e.get("desc", ""), e.get("default"), e.get("units", ""))
            target = fingerprint_new.get(fp)
            if target and target not in missing:
                candidates[f"{older}>{newer} {name}"] = target
    report.append(f"alias candidates (UNVERIFIED, not shipped): {len(candidates)}")
    report.extend(f"  candidate {k}: {v}" for k, v in sorted(candidates.items()))
    return {}


def main() -> int:
    import datetime as dt

    cfg = load_config()
    state = json.loads((CACHE / "state.json").read_text(encoding="utf-8")) if (CACHE / "state.json").exists() else {}

    source: dict = {}
    generated_hashes: dict = {}
    manifest_sources = []
    prefix_warnings: list[str] = []
    alias_report: list[str] = []
    vehicle_params: set[str] = set()
    if ARGS and ARGS.vehicle_params:
        vehicle_params = {line.strip() for line in Path(ARGS.vehicle_params).read_text().splitlines() if line.strip()}

    all_aliases: dict = {}
    for vehicle, vcfg in sorted(cfg["vehicles"].items()):
        series_meta: dict = {}
        for series in vcfg["series"]:
            key = f"{vehicle}.{series}"
            path = CACHE / f"apm.pdef.{vehicle}.{series}.xml"
            if not path.exists():
                raise SystemExit(f"missing cached pdef for {key}; run tools.fetch_meta first")
            if not SERIES_RE.match(series):
                raise SystemExit(f"bad series {series}")
            warnings: list[str] = []
            meta = normalize(path.read_bytes(), warnings)
            prefix_warnings.extend(f"{key}: {w}" for w in warnings)
            write_json(ROOT / "meta" / vehicle / f"{series}.json", meta)
            series_meta[series] = meta

            override_path = ROOT / "overrides" / f"{vehicle}.json"
            override_meta = json.loads(override_path.read_text(encoding="utf-8")) if override_path.exists() else {}
            texts = collect_texts(meta, override_meta)
            for t in texts:
                source[text_hash(t)] = t
            for name, entry in override_meta.items():
                if entry.get("source") != "generated":
                    continue  # only authored text counts as generated
                for field in GENERIC_FIELDS:
                    v = entry.get(field, "")
                    if v:
                        generated_hashes[text_hash(v)] = True

            src = state.get(key, {})
            manifest_sources.append(
                {
                    "vehicle": vehicle,
                    "series": series,
                    "url": src.get("url", ""),
                    "sha256": src.get("sha256") or file_sha256(path),
                    "params": len(meta),
                }
            )
            print(f"{key}: {len(meta)} params, {len(warnings)} prefix warnings")

        vehicle_alias = derive_aliases(series_meta, alias_report)
        if vehicle_alias:
            all_aliases[vehicle] = vehicle_alias

    write_json(ROOT / "source.json", source)
    write_json(ROOT / "aliases.json", all_aliases)
    write_json(ROOT / "generated.json", generated_hashes)

    # Draft manifest; release.py rewrites data_version/created at release time.
    locales = {}
    tm_dir = ROOT / "tm"
    if tm_dir.exists():
        for tm_file in sorted(tm_dir.glob("*.json")):
            locale = tm_file.stem
            tm = json.loads(tm_file.read_text(encoding="utf-8"))
            locales[locale] = {
                "total": len(source),
                "translated": len(tm),
                "reviewed": sum(1 for v in tm.values() if v.get("r") == 1),
                "provider": "claude-cli" if locale != "en" else "source",
            }
    manifest = {
        "schema": 1,
        "data_version": "unreleased",
        "created": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "license": "GPL-3.0",
        "sources": sorted(manifest_sources, key=lambda s: (s["vehicle"], s["series"])),
        "locales": locales,
        "min_argus": "3.15.0",
    }
    write_json(ROOT / "manifest.json", manifest)

    # Coverage report.
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# Coverage report", ""]
    lines.append(f"- source strings: {len(source)} unique English texts")
    lines.append(f"- generated (override) hashes: {len(generated_hashes)}")
    lines.append(f"- prefix collisions: {len(prefix_warnings)}")
    lines.extend(f"  - {w}" for w in prefix_warnings[:50])
    lines.append(f"- aliases: {sum(len(v) for v in all_aliases.values())}")
    lines.extend(f"  - {v} {k}: {t}" for v, m in all_aliases.items() for k, t in m.items())
    if alias_report:
        lines.append(f"- alias notes: {len(alias_report)}")
        lines.extend(f"  - {w}" for w in alias_report[:50])
    if vehicle_params:
        target = ARGS.vehicle if ARGS else None
        if target and target in cfg["vehicles"]:
            override_path_t = ROOT / "overrides" / f"{target}.json"
            covered = set(json.loads(override_path_t.read_text(encoding="utf-8"))) if override_path_t.exists() else set()
            for series in cfg["vehicles"][target]["series"]:
                meta = json.loads((ROOT / "meta" / target / f"{series}.json").read_text(encoding="utf-8"))
                missing = sorted(vehicle_params - set(meta))
                sims = [n for n in missing if n.startswith("SIM_")]
                lines.append(f"- real-vehicle names missing from {target} {series}: {len(missing)} ({len(sims)} SIM_*)")
                for n in missing:
                    tag = " [SIM]" if n.startswith("SIM_") else ""
                    if n in covered:
                        tag += " [override]"
                    lines.append(f"  - {n}{tag}")
        else:
            lines.append("- real-vehicle list given but no valid --vehicle; skipped")
    for locale, stats in sorted(manifest["locales"].items()):
        lines.append(
            f"- locale {locale}: {stats['translated']}/{stats['total']} translated, {stats['reviewed']} reviewed"
        )
    (OUT / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"source.json: {len(source)} strings; aliases: {sum(len(v) for v in all_aliases.values())}")
    print(f"coverage: out/coverage.md")
    return 0


ARGS = None


def cli() -> int:
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--vehicle-params",
        help="file of bare parameter names from a real vehicle; adds a missing-names section to the report",
    )
    ap.add_argument("--vehicle", help="vehicle the --vehicle-params list came from (copter/plane/rover/sub)")
    ARGS = ap.parse_args()
    return main()


if __name__ == "__main__":
    raise SystemExit(cli())
