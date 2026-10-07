---
name: Bug report
about: Something in AEGIS is broken or behaves unlike the docs
title: "[bug] "
labels: bug
assignees: ""
---

<!--
Before filing: AEGIS ships two labs (Demo 1, Demo 2) using static routing and
L2 switching only. OSPF / BGP / EVPN / VPNs are disabled on purpose — a report
that those are "missing" is not a bug (see README, "What this is — and what it
is not").
-->

## What happened

A clear, factual description. State what you expected and what you got.

## How to reproduce

1.
2.
3.

Command(s) or UI route used (`http://localhost:8000/…`):

## Environment

- AEGIS commit / tag:
- Host OS (e.g. Debian 13, Ubuntu 24.04):
- Docker: `docker --version`
- ContainerLab: `containerlab version`
- Install method: `sudo ./install.sh`
- Node/service involved (e.g. `demo-02` router, `aegis.service`):

## Evidence

Paste real output, not a summary. For grading issues, include the exact
`POST /api/sessions/{id}/submit` response (pass / fail / **refused**).

```
<paste output here>
```

## Did you reload after editing labs?

Lab definitions are cached in memory. If you edited a definition or grader, run:

```bash
curl -X POST http://localhost:8000/api/labs/reload
```
