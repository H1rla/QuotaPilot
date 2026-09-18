"""Typed failures for model-profile loading and enrichment."""


class CapabilityProfileError(Exception):
    """Base class for capability-profile failures."""


class ProfileLoadError(CapabilityProfileError):
    """A profile file could not be read or decoded safely."""


class ProfileValidationError(CapabilityProfileError):
    """Decoded profile data does not satisfy the strict schema."""


class UnsupportedProfileVersionError(ProfileValidationError):
    """The profile declares a schema version this build cannot consume."""


class AmbiguousProfileError(CapabilityProfileError):
    """Profiles provide ambiguous same-precedence metadata for one model."""
