"""Contract-level tests for the shared helpers.

The hash rule is the one thing every other file depends on: sha256 over the
exact UTF-8 English text, no normalization. A change here silently invalidates
every translation, so the expected digests are written out rather than computed.
"""

from __future__ import annotations

import json

from tools.common import file_sha256, is_canonical_int, read_json, text_hash, write_json


def test_text_hash_is_sha256_of_exact_utf8():
    assert text_hash("Battery capacity") == "83b4038b5ac431dbea75983c98b3cbf1c5e9df296572ae001a1c7400a9c71763"
    assert text_hash("é") == "4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c"
    assert text_hash("中文") == "72726d8818f693066ceb69afa364218b692e62ea92b385782363780f47529c21"


def test_text_hash_does_not_normalize_unicode_or_whitespace():
    assert text_hash("é") != text_hash("é")
    assert text_hash(" Battery capacity") != text_hash("Battery capacity")
    assert text_hash("Battery capacity\n") != text_hash("Battery capacity")


def test_is_canonical_int():
    assert is_canonical_int(1)
    assert is_canonical_int(1.0)
    assert not is_canonical_int(1.5)
    assert not is_canonical_int("1")


def test_write_json_keeps_unicode_and_sorts_keys(tmp_path):
    path = tmp_path / "nested" / "data.json"
    write_json(path, {"z": "中文", "a": 1})
    raw = path.read_text(encoding="utf-8")
    assert "中文" in raw
    assert "\\u4e2d" not in raw
    assert raw.index('"a"') < raw.index('"z"')
    assert read_json(path) == {"a": 1, "z": "中文"}


def test_write_json_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "data.json"
    write_json(path, {"a": 1})
    assert path.exists()
    assert not (tmp_path / "data.json.tmp").exists()


def test_file_sha256_hashes_bytes(tmp_path):
    path = tmp_path / "blob.bin"
    path.write_bytes(b"abc")
    assert file_sha256(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_read_json_rejects_non_object_only_when_caller_needs_dict(tmp_path):
    path = tmp_path / "list.json"
    path.write_text(json.dumps([1, 2]), encoding="utf-8")
    assert read_json(path) == [1, 2]
