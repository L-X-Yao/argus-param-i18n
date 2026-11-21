"""Assemble and publish a data release.

Usage:
  python -m tools.release --version 2026.11.1 --skip-publish   # build dist/ only
  git add ... && git commit && git push                          # commit the data
  python -m tools.release --version 2026.11.1 --publish-only     # tag + GitHub release

What it does:
1. rewrites manifest.json (data_version, created, fresh locale stats);
2. packs param_i18n/ (manifest, meta/, tm/, glossary/, aliases.json, overrides/)
   into dist/argus-param-i18n-<version>.tar.gz — source.json stays in the repo
   only, per the contract; the tarball has the single top-level param_i18n/
   directory the Argus fetch script expects;
3. writes dist/argus-param-i18n-<version>.tar.gz.sha256;
4. --publish-only (or a plain run on a clean tree) tags data-v<version> on the
   current HEAD — which must already contain the released data, hence the
   commit-first order above — and creates the GitHub release with the tarball,
   the checksum and the coverage report.

Publishing refuses a dirty working tree: the tag must point at a tree that
holds the very manifest and data the tarball was built from.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import subprocess
import sys
import tarfile
from pathlib import Path

from .common import DIST, LOCALES, OUT, ROOT, file_sha256, read_json, write_json

PACK_MEMBERS = ("manifest.json", "meta", "tm", "glossary", "aliases.json", "overrides")


def refresh_manifest(version: str) -> dict:
    source = read_json(ROOT / "source.json")
    manifest = read_json(ROOT / "manifest.json")
    manifest["data_version"] = version
    manifest["created"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    locales = {}
    for locale in LOCALES:
        tm_path = ROOT / "tm" / f"{locale}.json"
        if not tm_path.exists():
            continue
        tm = read_json(tm_path)
        prev = manifest.get("locales", {}).get(locale, {})
        locales[locale] = {
            "total": len(source),
            "translated": len(tm),
            "reviewed": sum(1 for v in tm.values() if v.get("r") == 1),
            "provider": prev.get("provider", "claude-cli" if locale != "en" else "source"),
        }
    manifest["locales"] = locales
    write_json(ROOT / "manifest.json", manifest)
    return manifest


def refresh_coverage(manifest: dict) -> None:
    """Keep the uploaded coverage report in step with the manifest.

    The tarball does not carry coverage.md, but the release asset does. A TM
    update that skips build_catalog would otherwise publish a report whose
    locale line still says the previous translated count.
    """
    path = OUT / "coverage.md"
    if not path.exists():
        return
    stats = manifest.get("locales", {})
    lines = path.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if line.startswith("- locale "):
            locale = line[len("- locale ") :].split(":", 1)[0]
            st = stats.get(locale)
            if st is not None:
                updated.append(
                    f"- locale {locale}: {st['translated']}/{st['total']} translated, {st['reviewed']} reviewed"
                )
                seen.add(locale)
                continue
        updated.append(line)
    for locale, st in sorted(stats.items()):
        if locale not in seen:
            updated.append(
                f"- locale {locale}: {st['translated']}/{st['total']} translated, {st['reviewed']} reviewed"
            )
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def build_tarball(version: str) -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / f"argus-param-i18n-{version}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        for member in PACK_MEMBERS:
            path = ROOT / member
            if not path.exists():
                raise SystemExit(f"missing pack member: {member}")
            tar.add(path, arcname=f"param_i18n/{member}")
    digest = file_sha256(out)
    (DIST / f"{out.name}.sha256").write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    return out


def publish(version: str, tarball: Path) -> None:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip()
    if dirty:
        raise SystemExit(
            "working tree not clean — commit and push the generated data before publishing,\n"
            "so the data-v tag points at the tree the tarball was built from"
        )
    tag = f"data-v{version}"
    proc = subprocess.run(["gh", "release", "view", tag], capture_output=True, text=True)
    if proc.returncode == 0:
        raise SystemExit(f"release {tag} already exists")
    notes_file = OUT / "release_notes.md"
    notes = [
        f"# Param i18n data {version}",
        "",
        f"- SHA256: `{file_sha256(tarball)}`",
        f"- Asset: `{tarball.name}` (SHA256 line file attached)",
        "- Pack layout and license: see README.md and docs/PARAM_I18N.md in L-X-Yao/argus.",
        "- Machine translation (`r: 0`) unless the manifest says otherwise; corrections land as TM edits plus a new data version.",
        "",
        "Coverage summary is attached as coverage.md.",
    ]
    manifest = read_json(ROOT / "manifest.json")
    notes.append("")
    notes.append("| vehicle | series | params |")
    notes.append("|---|---|---|")
    for s in manifest["sources"]:
        notes.append(f"| {s['vehicle']} | {s['series']} | {s['params']} |")
    for locale, st in sorted(manifest["locales"].items()):
        notes.append(f"\n- `{locale}`: {st['translated']}/{st['total']} translated, {st['reviewed']} reviewed ({st['provider']})")
    notes_file.write_text("\n".join(notes) + "\n", encoding="utf-8")
    coverage = OUT / "coverage.md"
    # --target main: gh creates the tag on the remote at the pushed main HEAD,
    # which must be the commit this tarball was built from.
    subprocess.run(
        ["gh", "release", "create", tag,
         "--target", "main",
         "--title", f"Param i18n data {version}",
         "--notes-file", str(notes_file),
         str(tarball), str(DIST / f"{tarball.name}.sha256")]
        + ([str(coverage)] if coverage.exists() else []),
        check=True,
    )
    print(f"published {tag}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="YYYY.MM.N, e.g. 2026.11.1")
    ap.add_argument("--skip-publish", action="store_true", help="build dist/ only, no tag or release")
    ap.add_argument("--publish-only", action="store_true",
                    help="skip build; publish dist/<version> from the committed tree")
    args = ap.parse_args()
    import re

    if not re.match(r"^\d{4}\.\d{2}\.\d+$", args.version):
        raise SystemExit("version must be YYYY.MM.N")

    if args.publish_only:
        tarball = DIST / f"argus-param-i18n-{args.version}.tar.gz"
        if not tarball.exists():
            raise SystemExit(f"{tarball} missing; build it first (run without --publish-only)")
        publish(args.version, tarball)
        return 0

    manifest = refresh_manifest(args.version)
    refresh_coverage(manifest)
    tarball = build_tarball(args.version)
    size = tarball.stat().st_size
    print(f"{tarball.name}: {size} B, sha256 {file_sha256(tarball)}")
    print(f"manifest: {len(manifest['sources'])} sources, locales: {sorted(manifest['locales'])}")
    if args.skip_publish:
        return 0
    publish(args.version, tarball)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
