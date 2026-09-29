import pytest

from datenspec.tcs3448 import (
    GAIN_FACTORS,
    capture_flags,
    full_scale,
    gain_factor,
    integration_time_ms,
)


def test_gain_factors_match_datasheet() -> None:
    assert GAIN_FACTORS == (
        0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048,
    )  # fmt: skip
    assert gain_factor(0) == 0.5
    assert gain_factor(12) == 2048


def test_integration_time() -> None:
    # (29 + 1) * (599 + 1) * 2.78 us = 50.04 ms
    assert integration_time_ms(29, 599) == pytest.approx(50.04)
    assert integration_time_ms(0, 0) == pytest.approx(0.00278)


def test_full_scale_is_capped_at_16_bit() -> None:
    assert full_scale(0, 99) == 100
    assert full_scale(29, 599) == 18000
    assert full_scale(255, 65534) == 65535


def test_clean_capture_is_not_suspect(make_capture) -> None:
    flags = capture_flags(make_capture())
    assert not flags.saturated
    assert flags.near_full_scale == ()
    assert not flags.suspect


def test_sat_flag_is_passed_through(make_capture) -> None:
    flags = capture_flags(make_capture(sat=True))
    assert flags.saturated
    assert flags.suspect


def test_near_full_scale_relative_to_settings(make_capture) -> None:
    # Full scale 18000: 16200 is exactly 90 %, 16199 is just below.
    raw = {"f1": 16200, "f2": 16199}
    capture = make_capture(raw=make_capture().raw.model_dump(exclude_none=True) | raw)
    flags = capture_flags(capture)
    assert flags.near_full_scale == ("f1",)
    assert flags.suspect
    assert capture_flags(capture, threshold=0.95).near_full_scale == ()


def test_optional_vis_channels_are_checked(make_capture) -> None:
    raw = make_capture().raw.model_dump(exclude_none=True) | {"vis_2": 17999}
    assert capture_flags(make_capture(raw=raw)).near_full_scale == ("vis_2",)
