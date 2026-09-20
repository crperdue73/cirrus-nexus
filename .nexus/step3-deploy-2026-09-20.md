# Nexus step 3 — real-topology deploy + digest citation (verified 2026-09-20 16:0x EDT)

## What was done
Ran the live prototype (backend/main.py, port 8000) and started a real lab session
via the app's own API — not a hand-built lab.

- POST /api/sessions/start?lab_id=tier-02-router-basics&student_name=Selina
- session_id: 480990d7  status: running
- nodes: pc-a (alpine:latest) + r1 (aegis/frr:latest)

## The verification (the point of step 3/5)
App-cited runtime digest:
  sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
Shipped pin (assets/frr-image.pin):
  layers_sha256=bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
===> byte-identical. The app cannot cite a state without the pinned substrate digest.

Earlier demo-01 session (4b935085) deployed and destroyed cleanly; cited
aegis-less:<sha> (demo lab uses alpine, not FRR — expected, not the pin).

## Steps 1/2/5 status re-verified
1. Build gate: install.sh now hashes Dockerfile.frr into label
   aegis.frr.dockerfile.sha256 and rebuilds on mismatch (absent label = mismatch).
   On-disk hash cce15a86... == image label cce15a86.... DONE, committed (git clean).
2. Cold rebuild: image rebuilt 2026-09-19T16:01:57-04:00, id acb8d8dc..., shipped
   as assets/aegis-frr-image.tar.gz with pin. DONE.
5. Runtime pin wired: _image_layers_sha + _resolve_container_digest resolve off
   the RUNNING container; absent digest -> status "refused", never a green grade.
   DONE. Proven live above.

## Steps still open
3. Remaining: deploy against ETHAN's topology (I asked; no reply yet) — our own
   lab proves the mechanism, his lab proves it on his subnet/ownership boundary.
   Ownership gate correctly refused to adopt his running clab labs (commit 3f53287).
4. Cold-host install.sh verification on a clean host — NOT done (no clean host).
