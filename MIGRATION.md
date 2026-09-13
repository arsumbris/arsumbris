# Migrating between versions

arsumbris is early alpha and under active development.
Breaking changes will happen.

This guide tells you how to move from one version to the next.

## How versioning works

- arsumbris has **one public version** (semver, `0.x` pre-1.0).
  - it names a coherent, tested set of the parts (engine + host + mcp).
  - it is a git tag applied across every part's public repo.
- Pre-1.0 bump rule:
  - **MINOR** = a break reached users (a wire/contract integer bumped, an on-disk format changed, a CLI or behaviour break).
  - **PATCH** = additive only (features, fixes, no integer bumps).

## Compatibility

- We test the **default shipped set** (engine + host + mcp at one version) for basic coherence.
- Mixing parts across versions is your responsibility.
  - the internal integer checks are the safety net: a detected mismatch is a loud refusal at startup rather than running mismatched parts.

## Per-version notes

<!-- Filled in as versioned releases ship. One section per version, newest first. -->

_No releases yet. The first tagged release will land its migration notes here._
