"""Typed failures for deterministic calibration data and replay."""


class CalibrationError(Exception):
    """Base class for calibration failures."""


class CalibrationLoadError(CalibrationError):
    """Scenario data could not be read or decoded safely."""


class CalibrationValidationError(CalibrationError):
    """Scenario data failed its strict schema."""
