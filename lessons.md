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

## 2026-09-18 — Aware datetime arithmetic is not automatically instant arithmetic
**What happened**: Subtraction of aware datetimes sharing one `ZoneInfo` could
measure local wall-clock hours across DST instead of actual elapsed seconds.
**Why**: Python preserves same-zone wall-time semantics in this case, which is
useful for calendars but wrong for quota durations and stale-age checks.
**Rule going forward**: Convert both operands to UTC before elapsed-time or
ordering calculations; convert to local time only for explicit calendar-day
semantics.

## 2026-09-18 — Missing capability metadata is not a model tier
**What happened**: Provider discovery exposes model IDs and effort strings but
does not currently provide QuotaPilot's relative power/cost/latency or prove
that arbitrary effort names are ranked.
**Why**: Inferring either from names would make routing brittle and silently
provider-specific.
**Rule going forward**: Preserve unknown candidates, require explicit power and
normalized effort order for ranking, and surface a typed no-route result until
an external capability definition supplies trustworthy metadata.

## 2026-09-18 — Capability policy needs both provenance and an expiry boundary
**What happened**: A local model profile can make incomplete provider catalogs
routable, but re-enriching or applying an old profile can accidentally make
manual policy look like current provider truth.
**Why**: A value alone does not retain who supplied it, when it was verified,
or whether it is still safe to apply.
**Rule going forward**: Fill only missing capability fields, preserve field
provenance across repeated enrichment, require exact model IDs, and keep
stale/future/unknown-freshness profiles visible but non-operative.

## 2026-09-18 — Approval must bind an action, not an advisory route
**What happened**: Phase 6 needed to turn an advisory recommendation into an
external process without treating an old model/quota choice as permanent
permission.
**Why**: Quota and capability state can change between planning, approval,
retry, and escalation; an escalation is also a materially different action.
**Rule going forward**: Bind approval to an inspectable plan, refresh coherent
quota and exact capabilities immediately before every attempt, stop on
material change, and require new approval for a changed escalation step.

## 2026-09-18 — Process output must be bounded while it is read
**What happened**: Capturing a full agent transcript before truncating it would
still allow memory growth and unnecessary secret retention.
**Why**: Post-hoc truncation does not bound buffering and subprocess pipes can
deadlock unless stdout and stderr are consumed concurrently.
**Rule going forward**: Drain both streams concurrently into fixed-size tails,
redact retained summaries, enforce a timeout, and terminate/reap the process on
timeout, cancellation, or transport failure.

## 2026-09-18 — Strict policy models need an explicit human-config boundary
**What happened**: Existing strict policy models correctly rejected YAML enum
strings, while a leaf-only merge could accidentally discard an unknown empty
mapping before `extra="forbid"` saw it.
**Why**: Human-readable YAML representations and partial nested configuration
are not identical to already-normalized in-process policy values.
**Rule going forward**: Parse only documented string/enum forms explicitly in
the config loader, preserve unknown and empty mappings through the merge, then
run the authoritative strict models once after precedence is resolved.

## 2026-09-18 — QML model roles must not shadow QQuickItem state
**What happened**: A history delegate and shared status component exposed a
role/property named `state`, which shadows QQuickItem's built-in state machine
property and caused a native crash while the full QML tree was instantiated.
**Why**: QML permits many dynamic names, but built-in item properties still
participate in meta-object construction and are not safe role aliases.
**Rule going forward**: Name domain status roles explicitly (`statusValue`,
`statusText`) and run both `qmllint` and full-engine smoke after adding a QML
delegate or shared component.
