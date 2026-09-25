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
- During alpha (versions ending in `-alpha`), every release steps the PATCH, and **any release may break**.
  - breaks still bump the internal integers, so mismatched parts refuse to start.
  - every break is listed below under its version, with what to do.
  - the MINOR/PATCH rule above applies once releases drop the `-alpha` suffix.

## Compatibility

- We test the **default shipped set** (engine + host + mcp at one version) for basic coherence.
- Mixing parts across versions is your responsibility.
  - the internal integer checks are the safety net: a detected mismatch is a loud refusal at startup rather than running mismatched parts.

## Per-version notes

<!-- Filled in as versioned releases ship. One section per version, newest first. -->

### 0.0.2-alpha

Internal integers: au-host mount contract **7 → 8**. au-engine wire schema stays 29, mcp wire stays 0.

Upgrade the whole set together: re-clone or `git fetch --tags && git checkout 0.0.2-alpha` in every part, then redo INSTALL.md steps 3-5 (the engine binary changes too).

#### au-host (mount contract 8)

A projection built against contract 7 is refused at load with `contract version mismatch`.

- **Re-declare the contract.** In each of your projection type-defs, set `contractVersion: 8` in its `projection-runtime-meta`.
- **`applyStructural` is gone from the pool contract.** `propose` is the only public pool write. A container that wrote structure directly calls `propose` instead.
- **`status-projection` is gone.** Bars use two kinds:
  - `bar-projection`: the bar itself. It is no longer a container; it holds its items in its own config and takes its orientation from its dock edge.
  - `bar-item-projection`: a widget inside a bar. Extend it for a status widget of your own.
  - the bar's `role`, the `bar-item` wrapper and the dock's reposition intent are gone. Dock edges hold `bar-projection` entries directly.
- **Renamed projections.** Update compositions and `repo.yaml` deps that name them:
  - the `status-bar` projection package is now `engine-status`.
  - bar items: `engine-status-bar-item`, `editor-bar-item`, `notification-bar-item`.
- **Discovery loads only code a type declares itself.** A concrete projection that only inherits its parent's `projection-runtime-meta`, declares several, or lacks a required one is rejected, with the reason. Give every concrete projection its own runtime meta.
- **`sandwich` and `dock` extend the new `frame-container` kind** and inherit its `center` field, which declares `container-slot`. No action needed:
  - a new rule on the sandwich center is written as `container-slot::au-host-sdk`.
  - an existing `sandwich-slot` around the center keeps working, since it is a subtype of `container-slot`.
  - `left` / `right` slots stay `sandwich-slot`.

#### au-engine (wire schema 29, additive)

No wire break. These change what existing calls return or accept:

- **A read or write that names no repo** now scopes to the served entry repo, not the shallowest one. Pass `repo` explicitly where you relied on the old default.
- **`instance_counts` with no arguments** now also counts meta instances (including the `au.engine.*` built-ins), so totals grow. Pass `origins` to count only what you want.
- **`remove_workspace_member`** refuses to remove the repo that contains the workspace.
- **A write under a symlinked directory** is refused.
- **Moving a top-level file** keeps a `[[a.md]]` link as written: a link without `/` is a name link.

#### Type system (may add diagnostics to your repos)

- **A union's `*` branch is reference-only.** An inline value there is now an error. Write it as a reference, or declare an inline branch in the union.
- **Meta inherits by subtype shadowing.** A subtype's meta replaces its parent's meta of the same type. Two parents contributing conflicting meta fire the new warning `meta-inheritance-conflict`.
- **`duplicate-meta-block` keys on the meta type's identity**, so two meta blocks of one type from different spellings are now caught.

#### au-engine-sdk

- **Divergent fields appear once per origin** in `type_closure` and `effective_fields`, so a field `name` can repeat. Key fields by `(name, origin)`, not `name` alone.
- **`untracked_files` is always present** on mutate results.
- **`PreviewMutationOp` gained `rename`, `move_dir` and `delete_dir`.** A `switch` over it that must be exhaustive needs the three new cases.

#### au-mcp-sdk

- **`redirects` is gone** from `listCapabilities` and the capabilities frame. It was always empty. Drop any reference to it. mcp wire stays 0.

#### Install

- `pnpm -r build` in au-host now also builds the shared-deps bundle. The separate `build:shared-deps` step is no longer needed.

### 0.0.1-alpha

The first public release. Nothing to migrate from.
