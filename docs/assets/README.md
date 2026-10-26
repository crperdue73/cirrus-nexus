# assets/ — images that ship with the docs

Everything here is generated from source in this tree. Nothing is a mock-up or a hand-drawn mock of
a screen that does not exist.

## `architecture-components.png`

- **What it is:** the component diagram in [`../architecture.md`](../architecture.md) — the same
  `mermaid` `flowchart TB` block, rendered to PNG.
- **How it was made:** `@mermaid-js/mermaid-cli` 12.0.0 against the bare mermaid block, theme
  `neutral`, white background, `-s 2`.
- **Authority:** the mermaid block in `docs/architecture.md` is the source of truth. If the PNG and
  the block disagree, the block is right and this file needs re-rendering.
- **Why not the live UI:** screenshots of a running AEGIS lab need a host with the containers
  actually deployed. The maintainer's lab host is not reachable from the box these docs are edited
  on, so there is no honest screenshot to commit yet. A rendered diagram of the real code paths is
  true; a mocked UI would not be.

To re-render after changing the diagram, extract the mermaid block from `docs/architecture.md` and run:

```bash
npx @mermaid-js/mermaid-cli@12 -i arch.mmd -o architecture-components.png -b white -s 2
```

## Is the committed PNG still in sync with the block?

Nothing automated proves it. The mermaid CLI does not embed its input text in the PNG (no text
chunks, no metadata — checked with a chunk walk on the committed file), so a stale render is
**byte-identical in shape** to a fresh one and CI cannot detect drift by hashing or grepping.

The check is a re-render and a diff, run by hand when `docs/architecture.md`'s diagram block changes:

```bash
# 1. extract the diagram block (the first mermaid fence in docs/architecture.md) to arch.mmd
# 2. re-render it as above, writing /tmp/architecture-components.png
sha256sum /tmp/architecture-components.png docs/assets/architecture-components.png
```

Same hash = the committed PNG really is that block. Different hash = re-render, eyeball the diff, and
commit the new PNG **in the same commit as the block change**.

Measured 2026-10-26: the committed PNG re-renders to an **identical** file — `sha256
5b0d87e74ef6a67ca81a0393ab07ade2cb59cc49a88cdf89bb2a47806c5dacfe`, 1568×1646, 110243 bytes — so at
that commit the block and the image agree. That is a measurement of one commit, not a standing
guarantee; re-run it after editing the block.

> Rendering as `root` needs Chromium's sandbox off. `mermaid-cli` takes a puppeteer config; with
> `{"args":["--no-sandbox"]}` in a JSON file passed as `-p puppeteer.json`, the command above
> works in a root shell. Rendering as a normal user needs no such flag.
