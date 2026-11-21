"""Download versioned apm.pdef.xml files into cache/ per config/sources.json.

Usage: python -m tools.fetch_meta [--force]

Idempotent: a cached file is kept unless --force. The URL actually used and its
SHA-256 are recorded in cache/state.json so the manifest can cite reality.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import urllib.error
import urllib.request

from .common import CACHE, LEGACY_XML_NAMES, MAX_XML_BYTES, USER_AGENT, load_config


def _download(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(MAX_XML_BYTES + 1)
    if len(raw) > MAX_XML_BYTES:
        raise ValueError(f"pdef larger than cap: {url}")
    if not raw.strip():
        raise ValueError(f"empty body: {url}")
    return raw


def fetch(force: bool = False) -> int:
    cfg = load_config()
    base = cfg["base_url"].rstrip("/")
    fallback = cfg["fallback_url"].rstrip("/")
    state_path = CACHE / "state.json"
    state: dict = {}
    if state_path.exists():
        import json

        state = json.loads(state_path.read_text(encoding="utf-8"))

    failures = []
    for vehicle, vcfg in sorted(cfg["vehicles"].items()):
        xml_name = vcfg["xml_name"]
        legacy = LEGACY_XML_NAMES.get(xml_name, xml_name)
        for series in vcfg["series"]:
            key = f"{vehicle}.{series}"
            path = CACHE / f"apm.pdef.{vehicle}.{series}.xml"
            if path.exists() and path.stat().st_size > 0 and not force:
                print(f"cached  {key} ({path.stat().st_size} B)")
                continue
            url = f"{base}/{xml_name}/stable-{series}/apm.pdef.xml"
            used = url
            try:
                raw = _download(url)
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
                print(f"miss    {key} via {url}: {exc}; trying legacy {legacy}", file=sys.stderr)
                try:
                    raw = _download(f"{fallback}/{legacy}/apm.pdef.xml")
                    used = f"{fallback}/{legacy}/apm.pdef.xml"
                    print(
                        f"WARNING {key}: series {series} absent upstream; cached the legacy master file "
                        "instead. The manifest will cite the legacy URL.",
                        file=sys.stderr,
                    )
                except (urllib.error.URLError, ValueError, OSError) as exc2:
                    failures.append((key, url, str(exc2)))
                    continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            import hashlib
            import json

            state[key] = {
                "url": used,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            }
            print(f"fetched {key} {len(raw)} B from {used}")

    if state:
        import json

        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if failures:
        for key, url, err in failures:
            print(f"FAIL {key} {url}: {err}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    args = ap.parse_args()
    return fetch(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
