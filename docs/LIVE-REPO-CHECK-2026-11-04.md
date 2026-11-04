# Live repository check — 2026-11-04

Purpose: close the gap the README's *Repository metadata* section names — `tools/check_repo_metadata.py`
checks the record against the tree, **not** what GitHub is serving. This note records the first measured
comparison of the live values. Nothing in the product was changed.

## How it was measured

Read-only, unauthenticated GitHub REST API from dept-dragon-tech (192.168.111.40/16) on 2026-11-04.
No token used, no write. Commands are the three `curl` lines already in README.md:513-521, plus the
branches endpoint for the HEAD sha.

## Results

| Claim | Record / tree | Live value | Match |
|---|---|---|---|
| description | `tools/check_repo_metadata.json` (AEGIS — hands-on networking labs for Cisco Net Eng I…) | identical string | yes |
| topics (9) | containerlab, docker, education, fastapi, frr, labs, networking, python, srlinux | same nine, same order | yes |
| license | Apache-2.0 (`LICENSE`) | `spdx_id: Apache-2.0` | yes |
| default branch | `main` | `main` | yes |
| archived | tree says active | `archived: false` | yes |
| HEAD | `d71c205` (local == origin/main, 0/0) | `main` head `d71c205` | yes |
| `pushed_at` | — | `2026-11-04T02:03:09Z` | consistent with the last push |

## Interesting / limits

- The API is reachable from this box (network is available; earlier runs did not say otherwise, they
  simply did not attempt it). So "we cannot see what GitHub serves" is no longer true for the public
  metadata routes — it remains true for anything needing a token (`workflow` scope) or a live AEGIS host
  (screenshots).
- This is a **point-in-time** measurement. Nothing compares it continuously; the repo's own note that
  "nothing in this repo could ever notice them going stale" still holds. A follow-up could add a
  read-only mode to `check_repo_metadata.py` that pulls these same public endpoints — that is a tool
  change, so it is written here as a plan, not done silently.
- Screenshots (README.md:401, docs/assets/README.md:14) remain blocked: they need a host with the
  containers running, which this box is not.
