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
