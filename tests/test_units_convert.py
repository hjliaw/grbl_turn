"""Saved-parameter conversion when the main-window unit selector changes."""

import pytest
from PySide6.QtCore import QSettings

import grbl_turn.config as config
from grbl_turn.units import Units, convert


@pytest.fixture
def isolated_settings(monkeypatch, tmp_path):
    ini = tmp_path / "settings.ini"
    monkeypatch.setattr(
        config, "settings",
        lambda: QSettings(str(ini), QSettings.Format.IniFormat))


def test_convert_lengths_but_not_pitch(isolated_settings):
    config.save_op_params("ext_turning", {"start_dia": 0.5, "feed": 3.0,
                                          "rpm": 600, "app_spindle": False})
    config.save_op_params("ext_thread", {"pitch_val": 20.0,
                                         "pitch_mode": "TPI",
                                         "first_depth": 0.003})

    config.convert_saved_params(Units.INCH, Units.MM)

    turning = config.load_op_params("ext_turning")
    assert float(turning["start_dia"]) == pytest.approx(12.7)
    assert float(turning["feed"]) == pytest.approx(76.2)
    assert int(turning["rpm"]) == 600          # not a length, untouched

    thread = config.load_op_params("ext_thread")
    assert float(thread["pitch_val"]) == pytest.approx(20.0)  # never converted
    assert thread["pitch_mode"] == "TPI"
    assert float(thread["first_depth"]) == pytest.approx(0.0762)


def test_convert_round_trip(isolated_settings):
    config.save_op_params("ext_turning", {"start_dia": 0.5})
    config.convert_saved_params(Units.INCH, Units.MM)
    config.convert_saved_params(Units.MM, Units.INCH)
    assert float(config.load_op_params("ext_turning")["start_dia"]) == \
        pytest.approx(0.5)


def test_convert_same_units_is_noop(isolated_settings):
    config.save_op_params("ext_turning", {"start_dia": 0.5})
    config.convert_saved_params(Units.MM, Units.MM)
    assert float(config.load_op_params("ext_turning")["start_dia"]) == 0.5


def test_convert_value():
    assert convert(1.0, Units.INCH, Units.MM) == pytest.approx(25.4)
    assert convert(25.4, Units.MM, Units.INCH) == pytest.approx(1.0)
    assert convert(3.7, Units.MM, Units.MM) == 3.7
    assert convert(3.7, Units.INCH, Units.INCH) == 3.7
