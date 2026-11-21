"""Validation must catch the failures that would reach Argus as bad data.

Every case here is a pack that would load but show a wrong number, a lost
placeholder parameter name, or a manifest whose coverage numbers lie.
"""

from __future__ import annotations

import pytest

from tools import validate
from tools.common import text_hash, write_json

CONFIG = {"vehicles": {"copter": {"series": ["4.6.3"]}}}


def _use_root(monkeypatch, tmp_path):
    monkeypatch.setattr(validate, "ROOT", tmp_path)
    monkeypatch.setattr(validate, "load_config", lambda: CONFIG)


def _write_manifest_tree(tmp_path):
    source_text = "Battery capacity"
    h = text_hash(source_text)
    write_json(tmp_path / "source.json", {h: source_text})
    write_json(tmp_path / "meta" / "copter" / "4.6.3.json", {"BATT_CAPACITY": {}})
    write_json(tmp_path / "tm" / "zh.json", {h: {"t": "电池容量", "r": 0}})
    manifest = {
        "schema": 1,
        "data_version": "2026.11.2",
        "license": "GPL-3.0",
        "min_argus": "3.15.0",
        "sources": [
            {
                "vehicle": "copter",
                "series": "4.6.3",
                "url": "https://example.invalid/apm.pdef.xml",
                "sha256": "a" * 64,
                "params": 1,
            }
        ],
        "locales": {"zh": {"total": 1, "translated": 1, "reviewed": 0}},
    }
    write_json(tmp_path / "manifest.json", manifest)
    return manifest


def test_number_problems_keeps_required_numbers_and_allows_ordinals():
    assert validate.mandatory_numbers("Set 4th mode to 2") == ["2"]
    assert validate.allowed_numbers("Set 4th mode to 2") == ["2", "4"]
    assert validate.number_problems("Set 4th mode to 2", "设置第4模式为2") == []


def test_number_problems_reports_dropped_and_invented_numbers():
    assert validate.number_problems("Set 2", "设置") == ["number 2 dropped"]
    assert validate.number_problems("Set 2", "设置 3") == ["number 2 dropped", "number 3 invented"]


def test_number_problems_allows_english_number_words_to_become_digits():
    assert "0" in validate.allowed_numbers("Set to zero")
    assert validate.number_problems("Set to zero", "设为 0") == []
    assert validate.number_problems("Set to zero", "设为 1") == ["number 1 invented"]


def test_number_problems_allows_a_month_name_to_become_its_number():
    assert "2" in validate.allowed_numbers("24th February 2026")
    assert validate.number_problems("February 2026", "2026 年 2 月") == []
    assert validate.number_problems("February 2026", "2026 年 3 月") == ["number 3 invented"]


def test_validate_tm_accepts_a_complete_entry(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    h = text_hash("Battery capacity")
    write_json(tmp_path / "tm" / "zh.json", {h: {"t": "电池容量", "r": 0}})
    errors: list = []
    warnings: list = []
    validate.validate_tm("zh", {h: "Battery capacity"}, {}, errors, warnings, strict=False)
    assert errors == []
    assert warnings == []


def test_validate_tm_warns_on_an_unknown_hash_and_strict_makes_it_an_error(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    h = text_hash("Old text")
    write_json(tmp_path / "tm" / "zh.json", {h: {"t": "旧文本", "r": 0}})
    errors: list = []
    warnings: list = []
    validate.validate_tm("zh", {}, {}, errors, warnings, strict=False)
    assert errors == []
    assert any("hash not in source.json" in w for w in warnings)

    errors = []
    warnings = []
    validate.validate_tm("zh", {}, {}, errors, warnings, strict=True)
    assert any("hash not in source.json" in e for e in errors)


def test_validate_tm_rejects_empty_translation(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    h = text_hash("Battery capacity")
    write_json(tmp_path / "tm" / "zh.json", {h: {"t": " ", "r": 0}})
    errors: list = []
    warnings: list = []
    validate.validate_tm("zh", {h: "Battery capacity"}, {}, errors, warnings, strict=False)
    assert any("empty translation" in e for e in errors)


def test_validate_tm_rejects_a_bad_reviewed_flag(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    h = text_hash("Battery capacity")
    write_json(tmp_path / "tm" / "zh.json", {h: {"t": "电池容量", "r": 2}})
    errors: list = []
    warnings: list = []
    validate.validate_tm("zh", {h: "Battery capacity"}, {}, errors, warnings, strict=False)
    assert any("r not 0/1" in e for e in errors)


@pytest.mark.parametrize(
    ("source", "translation", "needle"),
    [
        ("Use BATT_CAPACITY", "使用容量", "param name BATT_CAPACITY dropped"),
        ("Delete {n} logs", "删除 {count} 个日志", "placeholders changed"),
        ("Set 2 modes", "设置 3 种模式", "number 2 dropped"),
    ],
)
def test_validate_tm_rejects_lost_tokens(monkeypatch, tmp_path, source, translation, needle):
    _use_root(monkeypatch, tmp_path)
    h = text_hash(source)
    write_json(tmp_path / "tm" / "zh.json", {h: {"t": translation, "r": 0}})
    errors: list = []
    warnings: list = []
    validate.validate_tm("zh", {h: source}, {}, errors, warnings, strict=False)
    assert any(needle in e for e in errors)


def test_validate_tm_warns_on_generated_without_the_generated_marker(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    h = text_hash("Generated text")
    write_json(tmp_path / "tm" / "zh.json", {h: {"t": "生成文本", "r": 0, "s": "generated"}})
    errors: list = []
    warnings: list = []
    validate.validate_tm("zh", {h: "Generated text"}, {}, errors, warnings, strict=False)
    assert errors == []
    assert any("s=generated but hash not in generated.json" in w for w in warnings)


def test_validate_meta_accepts_a_well_formed_entry(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    write_json(
        tmp_path / "meta" / "copter" / "4.6.3.json",
        {"P": {"desc": "d", "human": "h", "range": [0, 1], "values": {"0": "a"}, "step": 1}},
    )
    errors: list = []
    warnings: list = []
    validate.validate_meta(errors, warnings)
    assert errors == []


def test_validate_meta_rejects_prefixes_and_bad_shapes(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    write_json(
        tmp_path / "meta" / "copter" / "4.6.3.json",
        {
            "ArduCopter:P": {"desc": "d", "human": "h"},
            "RANGE": {"range": [1]},
            "VALUES": {"values": ["not", "an", "object"]},
            "STEP": {"step": "one"},
            "NOT_OBJECT": [],
        },
    )
    errors: list = []
    warnings: list = []
    validate.validate_meta(errors, warnings)
    assert any("unstripped prefix" in e for e in errors)
    assert any("bad range" in e for e in errors)
    assert any("values not an object" in e for e in errors)
    assert any("step not numeric" in e for e in errors)
    assert any("entry not an object" in e for e in errors)


def test_validate_manifest_accepts_a_consistent_tree(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    _write_manifest_tree(tmp_path)
    errors: list = []
    warnings: list = []
    manifest = validate.validate_manifest(errors, warnings)
    assert errors == []
    assert warnings == []
    assert manifest["data_version"] == "2026.11.2"


def test_validate_manifest_reports_bad_header_and_counts(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    manifest = _write_manifest_tree(tmp_path)
    manifest["schema"] = 2
    manifest["license"] = "MIT"
    manifest["min_argus"] = "3"
    manifest["data_version"] = "2026-11"
    manifest["sources"][0]["sha256"] = "abc"
    manifest["sources"][0]["params"] = 2
    manifest["locales"]["zh"]["translated"] = 2
    write_json(tmp_path / "manifest.json", manifest)
    errors: list = []
    warnings: list = []
    validate.validate_manifest(errors, warnings)
    assert any("manifest schema != 1" in e for e in errors)
    assert any("license != GPL-3.0" in e for e in errors)
    assert any("min_argus not x.y.z" in e for e in errors)
    assert any("data_version not YYYY.MM.N" in e for e in errors)
    assert any("bad sha256" in e for e in errors)
    assert any("!= meta 1" in e for e in errors)
    assert any("manifest zh.translated=2" in e for e in errors)


def test_validate_manifest_reports_missing_source_row(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    manifest = _write_manifest_tree(tmp_path)
    manifest["sources"] = []
    write_json(tmp_path / "manifest.json", manifest)
    errors: list = []
    warnings: list = []
    validate.validate_manifest(errors, warnings)
    assert any("manifest sources" in e for e in errors)


def test_validate_manifest_warns_on_the_unreleased_placeholder(monkeypatch, tmp_path):
    _use_root(monkeypatch, tmp_path)
    manifest = _write_manifest_tree(tmp_path)
    manifest["data_version"] = "unreleased"
    write_json(tmp_path / "manifest.json", manifest)
    errors: list = []
    warnings: list = []
    validate.validate_manifest(errors, warnings)
    assert errors == []
    assert any("pre-release placeholder" in w for w in warnings)
