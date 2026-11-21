"""Normalization rules the Argus runtime depends on.

These tests use small pdef fragments rather than the cached real files: the
contract is about prefixes, the 16-character MAVLink name limit, canonical
numbers and text collection, not about any one firmware release.
"""

from __future__ import annotations

from tools.build_catalog import _canonical, collect_texts, derive_aliases, normalize, parse_pdef


def _xml(params: str, group: str = "Test") -> bytes:
    return f'<root><parameters name="{group}">{params}</parameters></root>'.encode()


def test_parse_pdef_reads_fields_and_codes():
    raw = _xml(
        '<param name="BATT_CAPACITY" humanName="Battery Capacity" documentation="Capacity in mAh">'
        '<field name="Range">0 10000</field>'
        '<field name="Units">mAh</field>'
        '<field name="Increment">1</field>'
        '<field name="Default">3300</field>'
        '<field name="Bitmask">0:First bit,1:Second bit</field>'
        '<values><value code="0">Disabled</value><value code="1">Enabled</value></values>'
        "</param>"
    )
    meta = parse_pdef(raw)
    entry = meta["BATT_CAPACITY"]
    assert entry["human"] == "Battery Capacity"
    assert entry["desc"] == "Capacity in mAh"
    assert entry["group"] == "Test"
    assert entry["range"] == [0.0, 10000.0]
    assert entry["units"] == "mAh"
    assert entry["step"] == 1.0
    assert entry["default"] == 3300.0
    assert entry["bitmask"] == {"0": "First bit", "1": "Second bit"}
    assert entry["values"] == {"0": "Disabled", "1": "Enabled"}


def test_parse_pdef_skips_unnamed_params_and_bad_numbers():
    raw = _xml(
        '<param documentation="no name"/>'
        '<param name="P" documentation="d">'
        '<field name="Range">not numbers</field>'
        '<field name="Increment">x</field>'
        '<field name="Default">y</field>'
        "</param>"
    )
    meta = parse_pdef(raw)
    assert set(meta) == {"P"}
    assert "range" not in meta["P"]
    assert "step" not in meta["P"]
    assert "default" not in meta["P"]


def test_canonical_turns_integral_floats_into_ints():
    entry = {"step": 1.0, "default": 3300.0, "range": [0.0, 10000.0]}
    assert _canonical(entry) == {"step": 1, "default": 3300, "range": [0, 10000]}
    entry = {"step": 0.5, "default": 1.5, "range": [0.0, 1.5]}
    assert _canonical(entry) == {"step": 0.5, "default": 1.5, "range": [0.0, 1.5]}


def test_normalize_strips_vehicle_prefix():
    raw = _xml(
        '<param name="ArduCopter:RTL_ALT" humanName="RTL Altitude" documentation="d"/>'
        '<param name="ArduPlane:RTL_ALT" humanName="Plane RTL" documentation="p"/>'
    )
    warnings: list = []
    meta, dropped = normalize(raw, warnings)
    assert set(meta) == {"RTL_ALT"}
    assert meta["RTL_ALT"]["human"] == "RTL Altitude"
    assert dropped == {}
    assert warnings  # the two prefixed forms differ; the first one is kept


def test_normalize_lets_a_bare_name_win_over_a_prefixed_one():
    raw = _xml(
        '<param name="ArduCopter:RTL_ALT" humanName="Prefixed" documentation="p"/>'
        '<param name="RTL_ALT" humanName="Bare" documentation="b"/>'
    )
    warnings: list = []
    meta, _ = normalize(raw, warnings)
    assert meta["RTL_ALT"]["human"] == "Bare"
    assert any("bare form replaces" in w for w in warnings)


def test_normalize_drops_bare_form_only_after_prefix_stripping():
    # ArduCopter:SIM_PLD_ALT_LIMIT is valid before stripping (29 chars) but its
    # bare name is 17 chars, which no MAVLink PARAM_VALUE can carry.
    raw = _xml('<param name="ArduCopter:SIM_PLD_ALT_LIMIT" documentation="d"/>')
    warnings: list = []
    meta, dropped = normalize(raw, warnings)
    assert meta == {}
    assert set(dropped) == {"SIM_PLD_ALT_LIMIT"}
    assert "dropped over-long/invalid name" in warnings[0]


def test_normalize_drops_illegal_characters_in_bare_name():
    raw = _xml('<param name="BAD-NAME" documentation="d"/>')
    warnings: list = []
    meta, dropped = normalize(raw, warnings)
    assert meta == {}
    assert set(dropped) == {"BAD-NAME"}


def test_normalize_ignores_identical_duplicate_forms():
    raw = _xml(
        '<param name="ArduCopter:RTL_ALT" humanName="RTL Altitude" documentation="d"/>'
        '<param name="RTL_ALT" humanName="RTL Altitude" documentation="d"/>'
    )
    warnings: list = []
    meta, _ = normalize(raw, warnings)
    assert list(meta) == ["RTL_ALT"]
    assert warnings == []


def test_collect_texts_includes_values_bitmask_and_overrides():
    meta = {
        "P": {
            "desc": "desc",
            "human": "human",
            "values": {"0": "zero", "1": "one"},
            "bitmask": {"0": "bit zero"},
        }
    }
    overrides = {"SIM_X": {"desc": "override desc", "human": "override human", "values": {"0": "ignored"}}}
    assert collect_texts(meta, overrides) == [
        "desc",
        "human",
        "zero",
        "one",
        "bit zero",
        "override desc",
        "override human",
    ]


def test_derive_aliases_reports_candidates_but_ships_none():
    old = {"OLD_NAME": {"human": "Same", "desc": "Same text", "default": 1, "units": "m"}}
    new = {"NEW_NAME": {"human": "Same", "desc": "Same text", "default": 1, "units": "m"}}
    report: list = []
    assert derive_aliases({"4.6.3": old, "4.7.1": new}, report) == {}
    assert any("alias candidates (UNVERIFIED, not shipped): 1" in line for line in report)
    assert any("4.6.3>4.7.1 OLD_NAME: NEW_NAME" in line for line in report)


def test_derive_aliases_does_not_alias_a_name_that_still_exists():
    old = {"OLD_NAME": {"human": "Same", "desc": "Same text", "default": 1, "units": "m"}}
    new = {
        "OLD_NAME": {"human": "Same", "desc": "Same text", "default": 1, "units": "m"},
        "NEW_NAME": {"human": "Same", "desc": "Same text", "default": 1, "units": "m"},
    }
    report: list = []
    derive_aliases({"4.6.3": old, "4.7.1": new}, report)
    assert any("alias candidates (UNVERIFIED, not shipped): 0" in line for line in report)
    assert not any(line.lstrip().startswith("candidate ") for line in report)
