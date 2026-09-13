# au-host

The malleable host UI over the typed graph (work in progress):
- [au-host](https://github.com/arsumbris/au-host)
  - currently a mono repo, holding
    - au-host-sdk and other contracts
    - default projections
  - will probably be split soon, expect breaking changes

An Electron app that mounts *projections* (views) over the au-engine graph.

It owns the frame and contract.
Projections own the content.

It does not ship the engine.
It supervises the `au` daemon and talks to it over the wire.


## Projections

A projection is the unit of UI, packaged as its own tiny engine repo.

Its type-def IS its config. There is no manifest and no registry.
The type it extends is its ROLE, and the host discovers each by querying the type system.

### A pane

The common case: a view that fills a slot. Extend `pane-projection`.

```yaml
# note-pane/type/note-pane.type.yaml
extends: pane-projection::au-host-sdk
fields:
  note?: String                     # an INSTANCE of this type is a configured view
meta:
  - type: projection-presentation-meta::au-host-sdk
    title: Note
  - type: projection-runtime-meta::au-host-sdk
    entry: ./dist/index.js          # the built ESM module
    contractVersion: 7              # must equal MOUNT_CONTRACT_VERSION in au-host-sdk
```

The module exports a `mount`. It returns its own cleanup.

```ts
// note-pane/src/index.ts
import { defineProjection } from '@arsumbris/au-host-sdk'

// MountFn = (container: HTMLElement, host: MountHost) => () => void
export default defineProjection({
  mount(container, host) {
    container.textContent = 'hello from note-pane'
    return () => container.replaceChildren()   // the unmount disposer
  },
})
```

Declare `au-host-sdk` as a dependency, build it, and it is mountable.

```yaml
# note-pane/.arsumbris/repo.yaml
name: note-pane
deps:
  - name: au-host-sdk
```

Note: after editing a projection, rebuild it and reload the pane. Optional per-pane live reload is available in dev for faster iteration.

### A container

Arranges other projections. Extend `spatial-container` (splits) or
`grouping-container` (stacks / tabs) and hold your children by reference.
The `container-kit` helpers give you drag / drop / slots,
so you arrange projections instead of reimplementing tabs or splits.

```yaml
# my-split/type/my-split.type.yaml
extends: spatial-container::au-host-sdk
fields:
  children: mountable::au-host-sdk*[]    # the projections it holds, by reference
```

### A bar

Aggregates every view of a role into a linear strip.
Extend `bar-projection` (e.g. `status-projection` fills the status bar).

### A placeholder

What an empty slot shows until content is picked. Extend `placeholder-projection`.

### What `host` gives you

`mount` receives a `host` (a `MountHost`) — the surface a projection works through.

```ts
mount(container, host) {
  const cfg = host.config as { note?: string }           // this pane's instance IS its config
  const where = host.entry.path                           // the workspace root on disk

  host.files.read('README.md').then(r => render(r.content))   // read the graph (engine-backed)
  host.files.write('notes/today.md', text)                    // ...and write it back

  const stop = host.selection.follow(sel => highlight(sel))   // follow sibling selection
  container.onclick = () => {
    host.selection.publish({ path: 'README.md' })                     // publish a selection
    host.intent.fire({ type: 'open-intent', path: 'notes/today.md' }) // ask the host to open something
    host.saveConfig({ note: 'edited' })                               // persist this pane's config
  }
  return () => stop()                                     // dispose subscriptions on unmount
}
```

Also on `host`:
- `workspace` — the members mounted beneath the entry (the workspace's repos).
- `focus` — which view is active, per scope.
- `viewStore` — per-viewer local state, kept outside the shared composition.
- `theme` — read, preview, and set the active theme.
- `components` — the swappable `<au-*>` component set.
- `preview` — a surface for transient preview content.


## Compositions

A composition arranges projection INSTANCES into a workspace.
It is its own type (not a projection). The host always opens a composition.

It is a flat POOL of instances plus a reference graph.
- `^: id` declares a pool entry.
- `[[^^id]]` references one.
- `[[type::repo]]` names a type.

```yaml
# a file tree beside a document
type: composition::au-host-sdk
windows:
  - "[[^^main]]"
projections:
  - ^: main
    type: window::au-host-sdk
    primary: true
    content: "[[^^grid]]"
  - ^: grid                          # a container splits the space
    type: bento::bento
    root:
      type: bento-node.branch::bento
      direction: row
      ratio: 0.22
      children:
        - "[[^^tree]]"
        - "[[^^doc]]"
  - ^: tree
    type: file-tree::file-tree
  - ^: doc
    type: note-pane::note-pane       # your projection, configured
```

The layout tree is the reference graph.


## The building blocks

**Containers** arrange other projections. No container is privileged, each owns only its own layout.
- `bento` (spatial splits), `tabs` (stacked groups), `dock` (edge chrome frame),
  `sandwich` (left / center / right), `column` (accordion), `bar` (linear aggregator).

**View-state channels** are how views coordinate.
- `intent` (typed actions, routed to a handler or broadcast), `focus` (the active view),
  `selection` (what is selected), `viewState` (standing per-view state).

**Components + themes** are swappable.
- `<au-*>` web components: a catalog declares the tags, a component-set implements them.
- Themes are instances over the CSS design tokens (`--au-*`). Swap either without touching views.


## Running it

The host is a pnpm workspace. Projections are built ESM; the app runs live.

```
pnpm -r build       # build the packages + projections
pnpm dev            # run the Electron shell
```

Projections run from their built `dist/`, so rebuild + reload after editing one:
```
pnpm --filter ./projections/<name> build
```
Optional per-pane live reload is available in dev for faster iteration.

On first run the launcher lets you pick or create a workspace from a template
(a starter that declares its `edit` / `discover` members), then starts the engine on it.


## Where it lives

- [au-host](https://github.com/arsumbris/au-host)
- Currently a monorepo:
  - `app/` the Electron shell.
  - `packages/` the SDKs + vocabulary (`au-host-sdk`, `intent`, `selection`, `style`, ...).
  - `projections/` the first-party views.
  - `templates/` shipped composition templates.
- The projections are first-party experiments, to be extracted over time.
