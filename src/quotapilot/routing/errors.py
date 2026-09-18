"""Typed failures for advisory routing."""


class RoutingError(Exception):
    """Base class for routing failures."""


class InvalidCapabilitiesError(RoutingError):
    """The capability set is internally inconsistent."""


class NoRoutableModelError(RoutingError):
    """No selectable model has enough metadata for a safe recommendation."""
