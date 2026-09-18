## 2026-09-18 — Persist from one privacy-safe canonical copy
**What happened**: Phase 3 serialized the parent snapshot first but later
serialized child objects again, so shallow metadata mutation could make one
transaction internally inconsistent; it also persisted structured account IDs
verbatim.
**Why**: Field-level frozen domain models do not deep-freeze metadata, and the
initial persistence design treated each SQL representation independently.
**Rule going forward**: At a persistence boundary, validate once, create one
defensive serialized copy, apply privacy transforms there, and derive every
JSON document and relational projection only from that copy.

## 2026-09-18 — A schema version number is not enough
**What happened**: A database with duplicate/malformed version rows or a
version-1 marker with missing tables could be accepted as current.
**Why**: Initialization read only the first version row and did not validate
the declared schema shape.
**Rule going forward**: Treat schema version state as an integrity assertion:
require exactly one integer row and validate the required tables/columns before
using an existing database.

## 2026-09-18 — Unknown quota semantics should degrade per calculation
**What happened**: Codex exposes useful normalized percentages, durations, and
reset times while leaving window kind and non-model scope undocumented.
**Why**: Treating the whole pool as either fully known or fully unusable would
discard safe calculations or invent unsupported semantics.
**Rule going forward**: Determine eligibility field by field. Report safe
remaining/time/daily values when their inputs exist, but keep expected pace,
state, and pressure UNKNOWN whenever their specific prerequisites are absent.

## 2026-09-18 — Calendar allocation needs explicit boundary rules
**What happened**: “Divide by remaining days” is ambiguous for partial current
days and reset-at-midnight timestamps.
**Why**: Hidden local-time and partial-day assumptions make tests and user
budgets non-deterministic.
**Rule going forward**: Use an explicit configured timezone and document
whether current/reset dates count before implementing calendar-based policy.
