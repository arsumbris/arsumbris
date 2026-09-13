# au-engine

The cross-repo graph engine over a typed file substrate:
- [au-engine](https://github.com/arsumbris/au-engine)
- [au-engine-sdk](https://github.com/arsumbris/au-engine-sdk)

It turns folders of markdown and YAML into a typed, queryable, live graph.


## Your repos with arsumbris

You scope different areas of work into their own git-tracked repo.

Each repo declares its identity and dependencies under `.arsumbris/repo.yaml`

```yaml
# health/.arsumbris/repo.yaml
name: health
remote: git@github.com:example/health.git
deps:
  - name: longevity-research  # a dependency, by registry name
  - name: ontology            # a dependency, by explicit remote
    remote: git@github.com:example/ontology.git
    ref: main
```

You start the engine on an entry repo,
and it reads that folders `.arsumbris/repo.yaml`.

It indexes every mounted repo (deps) and holds them as one graph in memory.
Change a file, and the graph updates.

If you want to work on multiple repos at once,
you can declare one workspace per repo `.arsumbris/workspace.yaml`.

```yaml
# health/.arsumbris/workspace.yaml
edit:                     # editable, live
  - health                # the containing repo, required
  - longevity-research
  - ontology
discover:                 # pinned, mounted for discovery
  - host-bundle
  - mcp-bundle
```

You can use cross-repo links to span the graph across repo boundaries.
`[[some file in another repo::other-repo-name]]`

The engine will parse markdown and YAML,
and the type system only applies on those filetypes for now.
But media files or other assets are also be indexed as untyped members.


## Arsumbris typing language

You define your own types in a small YAML typing language.

```yaml
# file: myType.type.yaml
# optional parent(s)
extends:
  - myParentTypeA
  - myParentTypeB
# optional fields
fields:
  myString: String
  myRegex: String{<regex>} # must match regex
  myNumber: Number
  myInteger: Number{integer} # must be whole number
  myPositive: Number{>=0} # must be positive
  myEnum: [a,b,c]
  myList: someType[]
  myCardinalList: someType[4..10] # must have 4-10 elements
  myInlineType: someOtherType # inline object matching this type
  myReference: someOtherType* # wikilink to file with this type
  myInlineOrRef: someOtherType& # either link or inline
  myTuple: (Number, Number)
  myUnion: <X | Y> # with */& - must match either X or Y
  myIntersection: <X & Y> # with */& - must match both X and Y
# optional sealed leaves
sealed:
  - closedSetOfChildTypesA # only the listed types may extend myType
  - closedSetOfChildTypesB
  - closedSetOfChildTypesC
# optional non-claimable marker
abstract: true # no instances allowed of this specific type
# optional body
body:
  - section: My Section
    fills: myInlineOrRef
    guidance: "Must contain a contribution to myReference"
    body:
      - section?: My Optional Subsection
# optional meta
meta:
  - type: my-type-annotation-meta
    annotation: "Data defined on the type definition"
```

And then have instances filling those types.

```md
# file: myInstance.md
---
type: myType
myString: "Value for my String"
...
# this will fire a diagnostic, only >=0 allowed
myPositive: -5 
# shape must match the definition of "someOtherType"
myInlineType: 
  foo: "abc"
  bar: 123
# that file must have the type "someOtherType" required by the field
myReference: [[instance-of-someOtherType]]
# gets filled in the body instead of frontmatter
myInlineOrRef:
---

# My Section
This section must be present or you get a diagnostic.
Here is the required body fill:
[[another-file-of-someOtherType:myInlineOrRef]]
This gets checked against the field myInlineOrRef
```

For the full specification,
please see [au-type-system](https://github.com/arsumbris/au-type-system).


## How you reach it

The `au` binary manages one daemon per workspace (start / stop / status).

- The daemon serves consumers over a Unix socket.
- Reads observe a version.
- Mutations go through one guarded write path.
- Subscriptions stream changes.

Bad data surfaces as diagnostics.
It never blocks a save or a read.

Boot it:

```
au daemon start .
```