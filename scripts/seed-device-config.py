#!/usr/bin/env python3
"""Seed the pre-graph device configs for a fresh arsumbris install.

The host's new-user setup runs BEFORE any engine/daemon, on no entry repo (the
engine only runs against the workspace setup creates). So these two device-global
files cannot be produced by the engine. This script writes them by plain IO.

It writes (idempotent merges, per-user, under ~/.arsumbris/, never committed):

  ~/.arsumbris/au-engine/config/repos.yaml
    the located-repo registry. every real repo under the install parent, so a
    materialized workspace's `discover:` resolves AND the create flow can list
    "dependencies you can also add". shape: `repos: - {name, path}`.

  ~/.arsumbris/au-host/config/workspace-template-repos.yaml
    the ordered template-repos the launcher reads for its gallery. seeded to point
    at the cloned au-defaults. shape: `repos: - {path}`.

  ~/.arsumbris/au-host/config/paths.yaml
    per-machine tool locations au-host reads to launch the engine + agent layer.
    seeded with ABSOLUTE paths so a Finder/Dock launch works regardless of the
    login-shell PATH. keys: `au` (engine binary), `au-mcp` (the CLI entry .ts, which
    au-host REQUIRES with no fallback), `node` (interpreter; spawned by name with no
    PATH mitigation), `binaries: {claude: ...}` (agent binary override). MERGE is
    append-only: existing keys are never clobbered, unknown keys/maps are preserved.

Discovery = walk the install parent for `*/.arsumbris/repo.yaml`. The parent holds
test/scratch subtrees too (au-engine/scenarios, dogfood, review copies, ...), so a
prune list keeps those out. On a clean install machine the noise is largely absent;
the prune list is the belt-and-braces for dev machines and for parts that ship test
fixtures.

Usage:
  seed-device-config.py [--root DIR] [--write] [--device-root DIR] [--au-path PATH]
  (default is a DRY RUN: prints what it would write, changes nothing.)
"""

import os
import shutil
import sys

HOME = os.path.expanduser("~")
DEFAULT_ROOT = os.path.join(HOME, "arsumbris")
DEFAULT_DEVICE_ROOT = os.path.join(HOME, ".arsumbris")

# where `au` / `node` / agent binaries commonly land, probed after PATH. mirrors the
# fallback set au-host itself uses, so the seeded path matches what au-host would find.
WELL_KNOWN_BIN_DIRS = [
    os.path.join(HOME, ".cargo", "bin"),   # `cargo install --path crates/au-cli` (INSTALL step 3)
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
]

# Subtree directory names pruned anywhere in the walk: build output, vcs, and the
# known test/fixture/dev locations that carry their own `.arsumbris/repo.yaml`.
PRUNE_DIRS = {
    ".git", "node_modules", "target", "dist", "build",
    "scenarios",        # au-engine test scenarios (hundreds of fixture repos)
    "dogfood", "e2e",   # au-host dev/test workspaces
    "testing", "tests", "fixtures", "__fixtures__", "examples", "vault",
}

# Whole sibling repos that are scratch / out-of-set (mirror of the release OUT list).
# A repo whose top-level dir name is here is skipped entirely.
PRUNE_REPOS = {
    "au-host--handover-review", "au-sandbox", "au-multi-repo-test", "au-test-vault",
    "data", "retired", "arscontexta", "au-intent", "au-index", "au-engine-ui",
}

TEMPLATE_REPO_NAME = "au-defaults"   # the first-party template-repo to seed the gallery with


def read_scalar(path, key):
    """Read a top-level `key: value` scalar from a small yaml file, or None."""
    try:
        for line in open(path, encoding="utf-8"):
            s = line.rstrip("\n")
            if s.startswith(key + ":"):
                return yaml_unquote(s[len(key) + 1:]) or None
    except (OSError, UnicodeDecodeError):
        pass
    return None


TEMPLATE_MANIFEST = "workspace-templates.yaml"


def read_template_paths(manifest):
    """The `path:` values under `templates:` in a template-repo manifest, as a set."""
    paths = set()
    try:
        in_templates = False
        for line in open(manifest, encoding="utf-8"):
            s = line.strip()
            if s.startswith("templates:"):
                in_templates = True
            elif in_templates and s.startswith("- path:"):
                paths.add(yaml_unquote(s[len("- path:"):]))
            elif in_templates and s.startswith("path:"):
                paths.add(yaml_unquote(s[len("path:"):]))
    except (OSError, UnicodeDecodeError):
        pass
    return paths


def discover_repos(root):
    """Walk `root` for repo roots (dirs holding `.arsumbris/repo.yaml`), pruned.

    Returns [(name, abspath, description_or_None)], sorted by name.
    """
    found = {}
    root = os.path.abspath(root)
    for dirpath, dirnames, _files in os.walk(root):
        # prune subtrees in place so os.walk does not descend into them.
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        # prune whole scratch sibling repos: only when listing root's direct children.
        if dirpath == root:
            dirnames[:] = [d for d in dirnames if d not in PRUNE_REPOS]
        # in a template-repo, prune its TEMPLATE folders: a template is a materialize
        # source (discovered via the template manifest), never an add-a-member dep.
        manifest = os.path.join(dirpath, TEMPLATE_MANIFEST)
        if os.path.isfile(manifest):
            tpaths = read_template_paths(manifest)
            dirnames[:] = [d for d in dirnames if d not in tpaths]

        repo_yaml = os.path.join(dirpath, ".arsumbris", "repo.yaml")
        if not os.path.isfile(repo_yaml):
            continue
        name = read_scalar(repo_yaml, "name")
        if not name:
            continue  # an aggregator/workspace-only .arsumbris with no repo identity
        desc = read_scalar(repo_yaml, "description")
        # first location wins on a name clash; report the collision.
        if name in found and found[name][0] != dirpath:
            print(f"  WARN: duplicate repo name '{name}': keeping {found[name][0]}, "
                  f"ignoring {dirpath}", file=sys.stderr)
            continue
        found[name] = (dirpath, desc)
    return sorted((n, p, d) for n, (p, d) in found.items())


def parse_repos_yaml(path):
    """Existing `repos: - {name, path}` list, as {name: path}. Tolerant, best-effort."""
    existing = {}
    if not os.path.isfile(path):
        return existing
    cur = None
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s.startswith("- name:"):
            cur = yaml_unquote(s[len("- name:"):])
        elif s.startswith("name:") and cur is None:
            cur = yaml_unquote(s[len("name:"):])
        elif s.startswith("path:") and cur is not None:
            existing[cur] = yaml_unquote(s[len("path:"):])
            cur = None
    return existing


def parse_template_repos(path):
    """Existing `repos: - path: X` entries in the host template config, in order."""
    paths = []
    if not os.path.isfile(path):
        return paths
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s.startswith("- path:"):
            p = yaml_unquote(s[len("- path:"):])
            if p and p not in paths:
                paths.append(p)
    return paths


def render_engine_repos(merged):
    lines = [
        "# ~/.arsumbris/au-engine/config/repos.yaml",
        "# Device-global located-repo registry. Seeded by INSTALL.md; extended live by the",
        "# create flow (registerLocations) and engine.register. Per-user, never committed.",
        "repos:",
    ]
    for name in sorted(merged):
        lines.append(f"  - name: {yaml_scalar(name)}")
        lines.append(f"    path: {yaml_scalar(merged[name])}")
    return "\n".join(lines) + "\n"


def render_template_repos(paths):
    lines = [
        "# ~/.arsumbris/au-host/config/workspace-template-repos.yaml",
        "# Ordered template-repos the launcher reads pre-graph for its create gallery.",
        "# Seeded by INSTALL.md; a user appends their own template-repo paths here.",
        "repos:",
    ]
    for p in paths:
        lines.append(f"  - path: {yaml_scalar(p)}")
    return "\n".join(lines) + "\n"


def find_binary(name, override=None):
    """Absolute path to an installed binary: explicit override, then PATH, then well-known dirs.

    Run from the terminal (INSTALL step 5), `shutil.which` sees the login-shell PATH, so the
    path we bake in is exactly what a GUI launch (with its minimal PATH) could not have found.
    """
    if override:
        return os.path.abspath(os.path.expanduser(override))
    onpath = shutil.which(name)
    if onpath:
        return os.path.abspath(onpath)
    for d in WELL_KNOWN_BIN_DIRS:
        cand = os.path.join(d, name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def existing_top_keys(path):
    """Top-level keys already present in a yaml file (col-0 `key:` lines). For append-only merge."""
    keys = set()
    if not os.path.isfile(path):
        return keys
    for raw in open(path, encoding="utf-8"):
        if not raw or raw[0] in " \t#-\r\n":   # indented (map/list child), comment, or blank
            continue
        if ":" in raw:
            keys.add(raw.split(":", 1)[0].strip())
    return keys


# YAML scalar (de)serialization for filesystem paths. A path may contain spaces, a '#'
# (which would otherwise start a comment and truncate the value), quotes, or backslashes,
# so double-quote + escape when the bare form would be unsafe, and reverse it exactly on
# read. This is the subset of YAML double-quoted rules that matters for paths.
_YAML_UNSAFE = set(" \t#:\"'{}[],&*?|<>=!%@`")


def yaml_scalar(v):
    """Serialize a string as a YAML scalar; double-quote + escape when unsafe bare."""
    unsafe = v == "" or v != v.strip() or v[0] in "-?" or any(c in _YAML_UNSAFE for c in v)
    if unsafe:
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v


def _yaml_unescape(body):
    """Unescape a double-quoted YAML scalar body (\\X -> X)."""
    out, i = [], 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body):
            out.append(body[i + 1]); i += 2
        else:
            out.append(body[i]); i += 1
    return "".join(out)


def yaml_unquote(s):
    """Inverse of yaml_scalar: unquote+unescape a quoted scalar, else strip an inline comment."""
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return _yaml_unescape(s[1:-1])
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    # a bare scalar never carries a space or '#' (we quote those), so a '#' here is a comment.
    return s.split("#", 1)[0].strip()


def render_paths(scalars, binaries, header):
    """Render the paths.yaml keys we own. `header` toggles the file-top comment block."""
    lines = []
    if header:
        lines += [
            "# ~/.arsumbris/au-host/config/paths.yaml",
            "# Per-machine tool locations read by au-host (main process). Seeded by INSTALL.md.",
            "# Absolute paths make GUI (Finder/Dock) launches work regardless of the login-shell PATH.",
            "# Per-user, never committed. Edit to override; the seeder never clobbers existing keys.",
        ]
    for k in ("au", "au-mcp", "node"):        # stable order
        if k in scalars:
            lines.append(f"{k}: {yaml_scalar(scalars[k])}")
    if binaries:
        lines.append("binaries:")
        for n, p in sorted(binaries.items()):
            lines.append(f"  {n}: {yaml_scalar(p)}")
    return ("\n".join(lines) + "\n") if lines else ""


def main(argv):
    root = DEFAULT_ROOT
    device_root = DEFAULT_DEVICE_ROOT
    write = False
    au_override = None
    it = iter(argv)
    for a in it:
        if a == "--root":
            root = os.path.abspath(next(it))
        elif a == "--device-root":
            device_root = os.path.abspath(next(it))
        elif a == "--au-path":
            au_override = next(it)
        elif a == "--write":
            write = True
        else:
            sys.exit(f"unknown arg: {a}")

    if not os.path.isdir(root):
        sys.exit(f"install parent not found: {root}")

    print(f"install parent: {root}")
    print(f"device root:    {device_root}")
    print(f"mode:           {'WRITE' if write else 'dry run (no changes)'}")
    print()

    repos = discover_repos(root)
    print(f"discovered {len(repos)} located repos (after pruning):")
    for name, path, desc in repos:
        rel = os.path.relpath(path, root)
        print(f"  {name:28} {rel}" + (f"   — {desc}" if desc else ""))

    # the template-repo is a plain directory holding workspace-templates.yaml (not an
    # engine repo itself), so point at its PATH, not a repo-name lookup.
    template_repo = os.path.join(root, TEMPLATE_REPO_NAME)
    if not os.path.isdir(template_repo):
        template_repo = None
        print(f"\n  WARN: template repo dir '{TEMPLATE_REPO_NAME}' not found under {root}; "
              f"the template gallery will have no first-party entry.", file=sys.stderr)

    engine_cfg = os.path.join(device_root, "au-engine", "config", "repos.yaml")
    host_cfg = os.path.join(device_root, "au-host", "config", "workspace-template-repos.yaml")

    existing = parse_repos_yaml(engine_cfg)
    merged = dict(existing)                         # preserve existing rows (and their locations)
    added = [n for n, p, _ in repos if n not in merged]
    conflicts = []                                  # (name, kept_existing_path, discovered_path)
    for name, path, _desc in repos:
        if name in merged and merged[name] != path:
            conflicts.append((name, merged[name], path))   # existing wins; record that we ignored discovery
        merged.setdefault(name, path)              # do not relocate an already-registered repo
    engine_text = render_engine_repos(merged)

    # host template config: MERGE too — preserve any template-repo paths the user added,
    # just ensure au-defaults is present. (idempotent; never clobbers user entries.)
    existing_tpl = parse_template_repos(host_cfg)
    tpl_paths = list(existing_tpl)
    tpl_added = False
    if template_repo and template_repo not in tpl_paths:
        tpl_paths.append(template_repo)
        tpl_added = True
    host_text = render_template_repos(tpl_paths)

    print(f"\nengine repos.yaml: {len(existing)} existing + {len(added)} new = {len(merged)} total")
    if added:
        print("  new: " + ", ".join(added))
    if conflicts:
        print(f"  WARNING: {len(conflicts)} repo(s) already registered at a DIFFERENT path — KEPT the existing "
              f"entry, did NOT use the discovered path:")
        for name, kept, found in conflicts:
            print(f"    {name}: kept {kept}  (discovery found {found})")
        print(f"    to adopt a discovered path, edit repos.yaml by hand or re-register that repo.")
    print(f"host workspace-template-repos.yaml: {len(existing_tpl)} existing"
          f"{f' + au-defaults' if tpl_added else ' (au-defaults already present)'}"
          f" = {len(tpl_paths)} total")

    # host paths.yaml: seed the installed tool locations so GUI launches resolve them.
    # append-only merge (never clobber existing keys; preserve unknown keys / maps).
    paths_cfg = os.path.join(device_root, "au-host", "config", "paths.yaml")
    present = existing_top_keys(paths_cfg)
    paths_exists = os.path.isfile(paths_cfg)

    own, warnings = {}, []
    au_bin = find_binary("au", au_override)
    if au_bin:
        own["au"] = au_bin
    else:
        warnings.append("`au` binary not found (checked PATH + ~/.cargo/bin + well-known dirs). "
                        "build+install the engine (INSTALL step 3) first, or pass --au-path. "
                        "au-host will PATH-probe as a fallback, so this is not fatal.")

    au_mcp_repo = merged.get("au-mcp")
    if au_mcp_repo:
        entry = os.path.join(au_mcp_repo, "src", "cli.ts")
        own["au-mcp"] = entry
        if not os.path.isfile(entry):
            warnings.append(f"au-mcp entry not found at {entry}. au-host REQUIRES 'au-mcp' with NO "
                            "fallback — a Dock launch hard-errors without it. verify au-mcp is cloned.")
    else:
        warnings.append("au-mcp repo not discovered under the install parent; cannot seed the REQUIRED "
                        "'au-mcp' entry (au-host has no fallback for it). clone au-mcp, then re-run.")

    node_bin = find_binary("node")
    if node_bin:
        own["node"] = node_bin
    else:
        warnings.append("`node` not found on PATH; leaving it unset (au-host defaults to 'node', which "
                        "a GUI launch under launchd's minimal PATH may fail to resolve).")

    own_binaries = {}
    claude_bin = find_binary("claude")
    if claude_bin:
        own_binaries["claude"] = claude_bin

    add_scalars = {k: v for k, v in own.items() if k not in present}
    add_binaries = own_binaries if ("binaries" not in present and own_binaries) else {}
    kept = [k for k in list(own) + (["binaries"] if own_binaries else []) if k in present]

    if paths_exists:
        n_add = len(add_scalars) + (1 if add_binaries else 0)
        print(f"host paths.yaml: exists, append-only merge; {n_add} key(s) to add"
              + (f", kept {', '.join(kept)}" if kept else ""))
    else:
        print(f"host paths.yaml: absent, would CREATE with {len(own) + (1 if own_binaries else 0)} key(s)")
    for w in warnings:
        print(f"  WARN: {w}", file=sys.stderr)

    if not write:
        print("\n--- would write (engine repos.yaml) ---")
        print(engine_text, end="")
        print("--- would write (host workspace-template-repos.yaml) ---")
        print(host_text, end="")
        print("--- host paths.yaml ---")
        if not paths_exists:
            print(f"(would CREATE {paths_cfg})")
            print(render_paths(own, own_binaries, header=True), end="")
        else:
            print(f"(MERGE into existing {paths_cfg}; present: {', '.join(sorted(present)) or '(none)'})")
            ap = render_paths(add_scalars, add_binaries, header=False)
            print("would APPEND:\n" + ap if ap else "nothing to add (our keys already present).\n", end="")
        print("\ndry run. re-run with --write to apply.")
        return

    for path, text in ((engine_cfg, engine_text), (host_cfg, host_text)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  wrote {path}")

    os.makedirs(os.path.dirname(paths_cfg), exist_ok=True)
    if not paths_exists:
        with open(paths_cfg, "w", encoding="utf-8") as f:
            f.write(render_paths(own, own_binaries, header=True))
        print(f"  wrote {paths_cfg}")
    else:
        ap = render_paths(add_scalars, add_binaries, header=False)
        if ap:
            prev = open(paths_cfg, encoding="utf-8").read()
            with open(paths_cfg, "a", encoding="utf-8") as f:
                f.write(("" if prev.endswith("\n") or not prev else "\n") + ap)
            print(f"  updated {paths_cfg} (appended {len(add_scalars) + (1 if add_binaries else 0)} key(s))")
        else:
            print(f"  {paths_cfg} already has our keys; nothing to add")


if __name__ == "__main__":
    main(sys.argv[1:])
