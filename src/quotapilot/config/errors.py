"""Typed configuration failures safe for CLI display."""


class ConfigError(Exception):
    """Base class for expected configuration failures."""


class ConfigLoadError(ConfigError):
    """The configuration source could not be read or decoded."""


class ConfigValidationError(ConfigError):
    """Configuration values do not satisfy the strict application schema."""
