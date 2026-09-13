# au-mcp

The agent lens over the typed graph (work in progress). It ships as a family of repos:
- [au-mcp](https://github.com/arsumbris/au-mcp) — the kernel daemon. Mechanism only, zero tools.
- [au-mcp-sdk](https://github.com/arsumbris/au-mcp-sdk) — the contract: wire protocol, plugin + adapter interfaces, base vocabulary.
- [au-mcp-core](https://github.com/arsumbris/au-mcp-core) — the bundled baseline plugins: the default agent surface (file ops, engine reads, intents) + the always-on floors.
- [au-mcp-adapter-cc](https://github.com/arsumbris/au-mcp-adapter-cc) / [au-mcp-adapter-codex](https://github.com/arsumbris/au-mcp-adapter-codex) — the harness adapters (Claude Code, Codex).

The daemon an agent talks to the graph through.
The engine surfaces the facts. au-mcp governs what the agent does with them.

- One daemon per workspace, paired 1:1 with the engine, over one socket.
- It serves many agent sessions. The kernel holds only mechanism, no tools and no policy.
- Everything the agent can do is a *plugin* on the contract SDK.


## Plugins

A plugin is its own tiny engine repo, discovered by type-query. No manifest, no registry.

There are two kinds.

### A tool

The agent-facing callable. A `mcp.tool` subtype whose fields ARE the call input.

```yaml
# type/write_file.type.yaml
extends: mcp.tool::au-mcp-sdk
fields:
  file_path: String     #: absolute path to write
  content: String       #: the full contents (overwrites)
meta:
  - type: plugin-runtime-meta::au-mcp-sdk
    entry: ./src/write-file.ts
    contractVersion: 0            # must equal PLUGIN_CONTRACT_VERSION in au-mcp-sdk
  - type: tool-access-meta::au-mcp-sdk
    broker: read-write            # none | read | read-write
  - type: tool-presentation-meta::au-mcp-sdk
    description: "Write a file, overwriting if it exists."
```

The module implements `createPlugin`. The metadata is derived from the type-def.

```ts
// src/write-file.ts
export function createPlugin(ctx) {
  return {
    async invoke({ file_path, content }) {
      // do the work through ctx (broker = the governed engine write seam)
      return { content: `wrote ${file_path}` }
    },
  }
}
```

### A hook

Kernel-internal, invisible to the agent. A `mcp.hook` subtype that fills one or more SHAPES.

- `observer` — watch the event stream, never deny.
- `mediator` — intercept a pending action: allow / deny / inject / ask.
- `stamper` — fold trustworthy metadata into a governed write.
- `session-start` — compute context to inject in front of the agent at open.

```yaml
# type/read-guard.type.yaml
extends: mcp.hook::au-mcp-sdk
meta:
  - type: plugin-runtime-meta::au-mcp-sdk
    entry: ./src/read-guard.ts
    shapes: [mediator]            # any of observer | mediator | stamper | session-start
    tier: floor                   # gate | floor | policy (earlier decides first)
    critical: true                # fail-closed at load
```

A mediator returns its decision.

```ts
// deny a write to a file the agent has not read
decide(action, ctx) {
  if (action.tool === 'write_file' && !ctx.hasRead(action.input.file_path))
    return { kind: 'deny', reason: 'read the file before overwriting it' }
  return { kind: 'allow' }
}
```


## What the agent gets at launch

Besides tools, a repo ships guidance and context.

- **skills** — triggered guidance, a `mcp.skill` instance (front-matter + a markdown body).
- **injects** — always-on context, a `mcp.inject` instance that seeds a graph walk.
- a `session-start` hook is the COMPUTED inject, recomputed per session.

```yaml
# skills/build-a-plugin.md
---
type: mcp.skill::au-mcp-sdk
name: build-a-plugin
description: How to build an au-mcp plugin. Use when adding a tool or hook.
---
# ...the instructions follow as markdown
```

An **agent-profile** bundles what one session sees: its `skills`, `inject`, `tools`,
`nativeToolAllowlist`, and `hooks`. Tool visibility is the profile's, resolved daemon-side.


## The pipeline + floors

Every agent action runs a fixed pipeline.

```
mediate -> act -> observe
```

- `mediate` — the mediators decide (allow / deny / inject / ask).
- `act` — the tool runs against the governed engine seam.
- `observe` — every event is appended to the session's ledger.

Governance is mostly OFF. Tools compete on merit. A few floors are always on
(shipped in au-mcp-core, fail-closed at load):

- **read-guard** — no writing a file you have not read.
- **tool-precondition** — a tool can require another ran first.
- **native-tool redirect** — the harness's own tools point at the governed equivalents.


## Reaching it

The engine is always reached through the daemon. A plugin never opens its own socket.

```
au-mcp start <workspace>        # one daemon, beside the engine's, on one socket
```

A harness binds through an ADAPTER. The adapter maps the harness's lifecycle hooks to
the daemon and declares its native tool surface. The kernel and plugins stay harness-agnostic.

```
# launch an agent against a workspace (Claude Code)
au-mcp-adapter-cc/bin/launch.ts   # materializes the skills/injects, prints the spawn command
```

Mediation fails OPEN if the daemon is unreachable (it never wedges the editor), and says so loudly.
