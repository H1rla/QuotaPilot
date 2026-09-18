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
