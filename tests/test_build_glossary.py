from __future__ import annotations

from tools.build_glossary import parse_reply, validate_glossary

KEYS = ["battery", "ESC", "RTL"]


def test_parse_reply_accepts_a_fenced_object():
    assert parse_reply('```json\n{"battery": "Batterie", "ESC": "ESC", "RTL": "RTL"}\n```') == {
        "battery": "Batterie",
        "ESC": "ESC",
        "RTL": "RTL",
    }


def test_validate_glossary_accepts_the_exact_key_set():
    assert validate_glossary({"battery": "Batterie", "ESC": "ESC", "RTL": "RTL"}, KEYS) == []


def test_validate_glossary_reports_missing_and_empty_terms():
    errors = validate_glossary({"battery": "", "ESC": "ESC"}, KEYS)
    assert any("keys differ" in e for e in errors)
    assert any("battery: empty" in e for e in errors)


def test_validate_glossary_keeps_identity_acronyms():
    errors = validate_glossary({"battery": "Batterie", "ESC": "电调", "RTL": "RTL"}, KEYS)
    assert "ESC: acronym changed" in errors[0]
