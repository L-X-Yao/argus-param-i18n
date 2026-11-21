"""Release packaging must produce the exact layout Argus fetches.

The tarball is the only artifact the application sees: one top-level
param_i18n/ directory, the six pack members, and a SHA-256 line that matches
the bytes. A release manifest must describe the files it was built from.
"""

from __future__ import annotations

import tarfile
from types import SimpleNamespace

import pytest

from tools import release
from tools.common import file_sha256, read_json, text_hash, write_json


def _use_root(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "DIST", tmp_path / "dist")


def _write_pack(tmp_path):
    write_json(tmp_path / "manifest.json", {"schema": 1, "sources": []})
    write_json(tmp_path / "meta" / "copter" / "4.6.3.json", {"P": {"desc": "d"}})
    write_json(tmp_path / "tm" / "zh.json", {text_hash("d"): {"t": "丁", "r": 0}})
    write_json(tmp_path / "glossary" / "zh.json", {"battery": "电池"})
    write_json(tmp_path / "aliases.json", {})
    write_json(tmp_path / "overrides" / "copter.json", {})


def test_build_tarball_has_one_top_level_directory_and_a_checksum(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    _write_pack(tmp_path)
    tarball = release.build_tarball("2026.11.2")
    assert tarball.name == "argus-param-i18n-2026.11.2.tar.gz"
    with tarfile.open(tarball, "r:gz") as tar:
        names = tar.getnames()
    assert names
    assert all(name == "param_i18n" or name.startswith("param_i18n/") for name in names)
    assert "param_i18n/manifest.json" in names
    assert "param_i18n/meta/copter/4.6.3.json" in names
    assert "param_i18n/source.json" not in names  # source stays in the repo only

    checksum = tmp_path / "dist" / "argus-param-i18n-2026.11.2.tar.gz.sha256"
    assert checksum.read_text(encoding="utf-8") == f"{file_sha256(tarball)}  {tarball.name}\n"


def test_refresh_manifest_recomputes_locale_stats(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    source = {text_hash("a"): "a", text_hash("b"): "b"}
    write_json(tmp_path / "source.json", source)
    write_json(tmp_path / "manifest.json", {"schema": 1, "data_version": "old", "sources": []})
    write_json(
        tmp_path / "tm" / "zh.json",
        {text_hash("a"): {"t": "甲", "r": 1}},
    )
    write_json(
        tmp_path / "tm" / "en.json",
        {text_hash("a"): {"t": "a", "r": 0}, text_hash("b"): {"t": "b", "r": 0}},
    )
    manifest = release.refresh_manifest("2026.11.2")
    assert manifest["data_version"] == "2026.11.2"
    assert manifest["created"].endswith("Z")
    assert manifest["locales"]["zh"] == {
        "total": 2,
        "translated": 1,
        "reviewed": 1,
        "provider": "claude-cli",
    }
    assert manifest["locales"]["en"]["provider"] == "source"
    assert read_json(tmp_path / "manifest.json")["data_version"] == "2026.11.2"


def test_publish_refuses_a_dirty_tree(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    monkeypatch.setattr(
        release.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=" M manifest.json\n"),
    )
    with pytest.raises(SystemExit, match="working tree not clean"):
        release.publish("2026.11.2", tmp_path / "dist" / "argus-param-i18n-2026.11.2.tar.gz")


def test_publish_refuses_an_existing_release(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(release.subprocess, "run", run)
    with pytest.raises(SystemExit, match="already exists"):
        release.publish("2026.11.2", tmp_path / "dist" / "argus-param-i18n-2026.11.2.tar.gz")
    assert any(call[:3] == ["gh", "release", "view"] for call in calls)
