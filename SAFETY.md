# Safety

arsumbris runs code on your machine. Read this before installing.

## It executes arbitrary code

By design, arsumbris runs code, not just data:
- **au-host** is an Electron app that loads and runs projection code (UI views over your graph).
- **au-mcp** runs plugins and tools that act on your files and your agent's behalf.
- **au-engine** builds a live graph over your files and runs on your machine.

Installing a part means running its code. That is the normal mode of operation, not an exploit.

## There is no sandboxing yet

This is an early alpha. There is **no security hardening or sandboxing** in place.
- Code you install runs with **your** user privileges.
- It can read and write your files, reach the network, and run commands, like any program you run.

## Third-party plugins and projections are the main risk

The framework is extensible: anyone can publish a plugin (au-mcp) or a projection (au-host).
- A third-party part runs with the same privileges as the first-party ones. Nothing isolates it.
- Treat installing someone else's plugin or projection like running any untrusted program.

Good practice before installing a third-party part:
- read what it does, or
- have your agent audit the package first (what it imports, what it touches, what it sends).

## First-party parts

The first-party parts (the repos in [INSTALL.md](INSTALL.md)) are the ones we build and test together.
They still execute code on your machine. The point above about no sandboxing applies to them too.
