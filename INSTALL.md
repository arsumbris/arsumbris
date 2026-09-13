# Install

How to stand up arsumbris from nothing: the engine, the host, and the agent layer.

> Early alpha. The parts are consumed from source (no build step for the JS repos); expect rough edges.
>
> **Tested on macOS only** for this release. Linux may work. Windows likely needs engine changes. Official Linux/Windows support is planned; you are welcome to try in the meantime.
>
> **Safety:** arsumbris runs code on your machine and has no sandboxing yet. Read [SAFETY.md](SAFETY.md) before installing.


## Layout: one parent, many sibling repos

Clone this entry repo to `~/arsumbris/arsumbris`. Every part is a sibling directory beside it under `~/arsumbris/`.

arsumbris is not one repo. It is a set of repos that sit **side by side** under one parent:

```
~/arsumbris/
  arsumbris/          # this repo — the entry point (docs, bundles)
  au-engine/          # the graph engine (the `au` binary)
  au-engine-sdk/
  au-host/
  au-mcp/
  ...
```

**The layout is the wiring, not a preference.**
- The engine resolves a workspace's member repos **sibling-first**: it finds `au-mcp` by scanning co-present repos under the parent.
- The JS packages depend on each other by **relative path** (`link:../au-engine-sdk`).

So every part must be a sibling directory under the same parent. `~/arsumbris/` is the default; any single parent works, as long as they are all in it.

Each part is its own repo, checked out under its **plain name** (`au-engine`, `au-mcp`, ...).


## 1. Prerequisites

- **git**
- **Rust** (stable) + `cargo` — builds the engine.
- **Node** + **pnpm** — au-host pins both in `au-host/package.json` (`packageManager: pnpm@11.1.1` and `engines.node: >=23`); use those for a reproducible build. With Corepack enabled, the pinned pnpm is selected automatically. **Tested on Node 24 LTS — use it.** Node ≥ 23 is the floor, but **Node 26 is not yet supported** (its install path is currently broken). The standalone JS repos run as TypeScript source (node type-stripping, no build); au-host builds (see step 4).
- **An agent harness** *(optional — only for the agent layer)* — **Claude Code** or **Codex** work out of the box (via `au-mcp-adapter-cc` / `au-mcp-adapter-codex`). Any other model or harness needs an adapter. The engine and host run without one; you just won't get agent capabilities until a harness is connected.
- **macOS: Xcode Command Line Tools** (`xcode-select --install`) — needed to build the engine, and provides the `python3` the setup script (step 5) uses. Most developers already have them.


## 2. Clone the repos

Into the same parent as this repo (`~/arsumbris/`), one sibling directory per part:

```sh
cd ~/arsumbris
VERSION=0.0.1-alpha   # the release tag to install (see VERSION.md); pin every part to the same one
for r in \
  au-engine au-engine-sdk au-type-system \
  au-host \
  au-mcp au-mcp-sdk au-mcp-core au-mcp-adapter-cc au-mcp-adapter-codex \
  au-type-codegen \
  au-base-types au-weave au-agent-guides au-rules au-writing-style au-skills au-govern au-competency au-ingest au-tree-research \
  au-defaults
do
  git clone --branch "$VERSION" https://github.com/arsumbris/"$r".git "$r"
done
```

Every part is checked out at the same release tag (`$VERSION`), so you install one coherent version, not a mix of branch HEADs. The repos are public, so this needs only git, no GitHub account. Contributors can swap in the SSH URL (`git@github.com:arsumbris/$r.git`).

What each is (see [README.md](README.md) for the layer overview):
- **au-engine** / **au-engine-sdk** — the graph engine + its TS client.
- **au-type-system** — the type-system specification.
- **au-host** — the Electron host UI (its own pnpm workspace: app + SDK + framework + projections).
- **au-mcp** / **au-mcp-sdk** — the agent kernel daemon + its contract.
- **au-mcp-core** — the baseline plugins (default tools + governance floors).
- **au-mcp-adapter-cc** — the Claude Code adapter.
- **au-mcp-adapter-codex** — the Codex CLI adapter.
- **au-type-codegen** — generates TS from engine type-defs (used by the codegen scripts).
- **the knowledge layer** — first-party knowledge-work capabilities (content + skills, no build step):
  - `au-base-types` (base ontology) and `au-weave` (the weaving layer over it).
  - `au-rules`, `au-writing-style`, `au-agent-guides`, `au-skills`, `au-govern`, `au-competency` (agent rules, authoring, governance).
  - `au-ingest` (files → typed source notes), and the `au-tree-research` feature package.
- **au-defaults** — the default composition layer: the aggregator bundles (host-bundle, mcp-bundle) and the starter workspace templates.


## 3. Build the engine

```sh
cd ~/arsumbris/au-engine
cargo build --release
```

Put the resulting `au` binary on your PATH (it is the `au-cli` crate):

```sh
cargo install --path crates/au-cli
```

See [au-engine.md](au-engine.md) and au-engine's own README for the daemon commands and the optional faster linker.


## 4. Install the JS dependencies

The JS repos resolve each other as siblings, so they must all be cloned first (step 2). Install per repo with **pnpm**, using `--frozen-lockfile` so you get the exact vetted dependency set:

```sh
cd ~/arsumbris
for r in au-engine-sdk au-mcp au-mcp-sdk au-mcp-core au-mcp-adapter-cc au-mcp-adapter-codex au-type-codegen; do
  (cd $r && pnpm install --frozen-lockfile)
done
cd ~/arsumbris/au-host && pnpm install --frozen-lockfile   # au-host is its own workspace
```

`--frozen-lockfile` reinstalls exactly what each release tag locked (no resolution, no silent upgrades). It requires every repo above to carry a committed, in-sync lockfile — all of them do. Do **not** add `--ignore-scripts`: au-host needs the native `node-pty` build (see the `rebuild:native` step below), and that is separately gated by au-host's `allowBuilds` install-script allowlist.

The standalone repos have **no build step** — they are consumed directly as TypeScript source (run via node type-stripping). Each repo's README covers its own scripts.

**au-host is the exception: it builds.** After `pnpm install`, rebuild the native terminal module, then build the host + its projections:

```sh
cd ~/arsumbris/au-host
pnpm --filter app exec install-electron  # fetch Electron's runtime (Electron 42 no longer downloads it on install)
pnpm --filter app rebuild:native         # rebuild node-pty for Electron + fix its helper perms
pnpm -r build                            # the Electron app + all projections
pnpm --filter app build:shared-deps      # the single served shared-dep bundle
```

`install-electron` is **required**: as of Electron 42 the runtime (the Electron binary + Chromium and its license notices) is no longer downloaded during `pnpm install`, so the host build fails without this explicit step. It is Electron's own supported downloader.

`rebuild:native` is **required**: au-host runs terminals (and agent CLI sessions) through node-pty, a native module that must be rebuilt against Electron's runtime. On macOS it also repairs the terminal helper's execute bit (a known node-pty packaging bug). Run it after `pnpm install` — an install with `--ignore-scripts` skips the native step, so run it explicitly. It is idempotent and a no-op-repair on non-macOS.

The host serves each projection's built ESM; projections externalize the shared deps (React + the `au-*-sdk`s) and resolve them at runtime via a generated import map. (In dev, `pnpm dev` runs projections from a vite dev server instead.)


## 5. Seed the device config

The host's new-user setup runs **before any engine or daemon**, on no workspace yet (the engine only runs against the workspace setup creates). So it reads two device-global files by plain IO, and they must exist first. This step writes them from the repos you just cloned.

Run from this entry repo (`~/arsumbris/arsumbris`):

```sh
cd ~/arsumbris/arsumbris
python3 scripts/seed-device-config.py            # dry run: prints what it would write
python3 scripts/seed-device-config.py --write     # apply
```

If your parent directory is not `~/arsumbris`, pass it: `--root /path/to/parent`.

This writes, under `~/.arsumbris/` (per-user device state, never committed):

- `~/.arsumbris/au-engine/config/repos.yaml` — every located repo (`name` → `path`), so a new workspace's members resolve and the create flow can offer them as addable dependencies.
- `~/.arsumbris/au-host/config/workspace-template-repos.yaml` — the template-repos the launcher reads for its create gallery, seeded to point at the cloned `au-defaults`.
- `~/.arsumbris/au-host/config/paths.yaml` — absolute paths to the tools au-host launches: the `au` engine binary, the `au-mcp` CLI entry, `node`, and your agent binary (`claude`). Seeding these makes a **Finder/Dock launch** work out of the box, where the app's PATH differs from your terminal's.

All three are **idempotent**: re-running preserves the entries you or the app added and only fills in what's missing. (The two `repos` files are regenerated, so hand-added comments in them aren't kept; `paths.yaml` is merged in place.) You can append your own template-repo paths to the second file later.

Run this **after** step 3 (so the `au` binary exists to record its path). If `au` is not found, the seeder warns and skips that key — pass `--au-path /abs/path/to/au` to set it explicitly, or install the engine first. au-host also probes your PATH as a fallback.


## 6. Launch the host

> **Agents running this guide: stop here.** This is the last step, and it is the user's to run.
> `pnpm dev` starts the desktop app the user interacts with (a long-running GUI). Do **not** launch it
> yourself. Report that the install is complete and hand the user the command below to run themselves. Report this exact command, no extra flags or anything.

The install is done. To start arsumbris, run:

```sh
cd ~/arsumbris/au-host
pnpm dev
```

On the first run there is no workspace yet, so the host opens the **launcher**: pick a
starter template, name it, and it materializes a workspace and starts the engine on it.

**If a terminal or agent session fails to open** (e.g. `posix_spawnp failed`, or no shell
appears), the node-pty helper likely lost its execute bit. Re-run the native rebuild and
restart the app:

```sh
cd ~/arsumbris/au-host
pnpm --filter app rebuild:native
```

Then quit and relaunch au-host (a running app may still hold the old, broken module).


## The bundles

The **au-defaults** repo holds two aggregator repos:
- **host-bundle** — names the host's full UI closure (projections + first-party vocabulary).
- **mcp-bundle** — names the agent layer's type-def owners.

A workspace names a bundle in its `.arsumbris/workspace.yaml` (`discover:` / `primary:`) to pull the whole member set in at once, instead of listing every repo. See [au-engine.md](au-engine.md) for workspace declaration.


## What a release is

A release is one coherent, tested set of the parts, named by a single version.

- The version is applied as a **git tag of the same name on every part's public repo.**
  - so "which commits are in version X?" = each public repo's tag `X`.
- [VERSION.md](VERSION.md) is a generated record of the current release: the version, each part's tagged commit, and its internal wire/contract integer.
  - it is written by the release, never hand-edited.

## Version + compatibility

- Install a **version**, not individual parts. Check out the same release tag across the parts.
- We test the **shipped set** (engine + host + mcp at one version) for basic coherence.
- Mixing parts across releases is your responsibility.
  - the safety net is the internal integer checks: a detected version mismatch is a **loud refusal at startup** rather than running mismatched parts.
- Breaking changes between versions are documented in [MIGRATION.md](MIGRATION.md).