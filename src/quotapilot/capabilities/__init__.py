"""Versioned capability-profile loading and deterministic enrichment."""

from quotapilot.capabilities.enrichment import CapabilityEnricher, capability_views
from quotapilot.capabilities.errors import (
    AmbiguousProfileError,
    CapabilityProfileError,
    ProfileLoadError,
    ProfileValidationError,
    UnsupportedProfileVersionError,
)
from quotapilot.capabilities.loader import default_profile_directory, load_profile
from quotapilot.capabilities.models import (
    MetricProvenance,
    ModelCapabilityView,
    ModelProfile,
    ModelProfileDocument,
    ProfileFreshness,
    ProfileMatch,
    ProvenanceConfidence,
    ProvenanceSource,
)
from quotapilot.capabilities.registry import ModelProfileRegistry

__all__ = [
    "AmbiguousProfileError",
    "CapabilityEnricher",
    "CapabilityProfileError",
    "MetricProvenance",
    "ModelCapabilityView",
    "ModelProfile",
    "ModelProfileDocument",
    "ModelProfileRegistry",
    "ProfileFreshness",
    "ProfileLoadError",
    "ProfileMatch",
    "ProfileValidationError",
    "ProvenanceConfidence",
    "ProvenanceSource",
    "UnsupportedProfileVersionError",
    "capability_views",
    "default_profile_directory",
    "load_profile",
]
