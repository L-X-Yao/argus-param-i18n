"""The authored aliases must point at real, non-ambiguous newer parameters."""

from __future__ import annotations

import json
import re

from tools.common import ROOT, read_json

ALIASES = read_json(ROOT / "aliases.json")
NAME = re.compile(r"^[A-Za-z0-9_]{1,16}$")


def _meta(vehicle: str) -> dict[str, dict]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (ROOT / "meta" / vehicle).glob("*.json")
    }


def test_alias_names_are_valid_and_not_self_mapped():
    for vehicle, mapping in ALIASES.items():
        assert isinstance(mapping, dict), vehicle
        for old, new in mapping.items():
            assert NAME.fullmatch(old), (vehicle, old)
            assert NAME.fullmatch(new), (vehicle, new)
            assert old != new, (vehicle, old)


def test_every_target_exists_and_the_old_name_is_gone_from_that_series():
    for vehicle, mapping in ALIASES.items():
        series = _meta(vehicle)
        for old, new in mapping.items():
            target_series = [name for name, meta in series.items() if new in meta]
            assert target_series, (vehicle, old, new, "target missing")
            assert all(old not in series[name] for name in target_series), (vehicle, old, new, "old still present")


def test_no_alias_points_at_another_alias():
    for vehicle, mapping in ALIASES.items():
        assert not (set(mapping.values()) & set(mapping)), vehicle


def test_confirmations_from_the_2026_11_22_review_are_present():
    expected = {
        "copter": {
            "PHLD_BRAKE_RATE": "PHLD_BRK_RATE",
            "PSC_ACCZ_SMAX": "PSC_D_ACC_SMAX",
            "PSC_JERK_XY": "PSC_NE_JERK",
            "PSC_JERK_Z": "PSC_D_JERK",
            "TELEM_DELAY": "MAV_TELEM_DELAY",
            "WPNAV_JERK": "WP_JERK",
            "WPNAV_RFND_USE": "WP_RFND_USE",
            "WPNAV_TER_MARGIN": "WP_TER_MARGIN",
        },
        "plane": {
            "Q_P_ACCZ_SMAX": "Q_P_D_ACC_SMAX",
            "Q_P_JERK_XY": "Q_P_NE_JERK",
            "Q_P_JERK_Z": "Q_P_D_JERK",
            "TELEM_DELAY": "MAV_TELEM_DELAY",
        },
        "rover": {"TELEM_DELAY": "MAV_TELEM_DELAY"},
        "sub": {
            "NET_ENABLED": "NET_ENABLE",
            "PSC_ACCZ_SMAX": "PSC_D_ACC_SMAX",
            "PSC_JERK_XY": "PSC_NE_JERK",
            "PSC_JERK_Z": "PSC_D_JERK",
            "SIM_WIND_T_": "SIM_WIND_T",
            "WPNAV_JERK": "WP_JERK",
            "WPNAV_RFND_USE": "WP_RFND_USE",
            "WPNAV_TER_MARGIN": "WP_TER_MARGIN",
        },
    }
    for vehicle, mapping in expected.items():
        for old, new in mapping.items():
            assert ALIASES[vehicle].get(old) == new, (vehicle, old, new)


def test_family_renames_are_complete():
    """SRx_* -> MAV(x+1)_*, CAM_* -> CAM1_*, SIM_GPS_JAM -> SIM_GPS1_JAM."""
    for vehicle in ALIASES:
        series = _meta(vehicle)
        old_series = "4.6.3" if "4.6.3" in series else "4.5.3"
        new_series = "4.7.1"
        if old_series not in series or new_series not in series:
            continue
        old, new = series[old_series], series[new_series]
        for name in old:
            target = None
            match = re.match(r"^SR(\d+)_(.+)$", name)
            if match:
                target = f"MAV{int(match.group(1)) + 1}_{match.group(2)}"
            elif name.startswith("CAM_"):
                target = "CAM1_" + name[len("CAM_"):]
            elif name == "SIM_GPS_JAM":
                target = "SIM_GPS1_JAM"
            if target and target in new and name not in new:
                assert ALIASES[vehicle].get(name) == target, (vehicle, name, target)
