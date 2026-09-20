# Proof — COMPOSITE REHEARSAL: cold-host install THEN deploy on the SAME fresh host

Date: 2026-09-20 ~05:0x–05:2x EDT (hour 01:00 nexus cron)
Driver: Selina
Status: COMPOSITE CLOSED — this is the exit-bar rehearsal.

## Why
STATUS.md at hour-close 2026-09-20 00:0x named the ONE thing not yet exercised
end-to-end in a single continuous run: cold-host install, THEN deploy the
prototype on that SAME fresh host, with the app citing the digest there. Every
individual step was already done; this was the composite. This hour produced it.

## Harness
    docker run --rm --privileged -v <aegis-project>:/src:ro debian:12 bash -c '<script>'
    Fresh debian:12. NO docker, NO containerlab at start (verified bare).
    Pre-seeded ONLY: {"storage-driver":"vfs"} in /etc/docker/daemon.json.
      -> HARNESS CONSTRAINT, not an install.sh change. Nested docker (docker-in-
         docker) cannot mount overlay-on-overlay; vfs is the nested-docker
         workaround. On real hardware the default overlay2 is correct and this
         file is unnecessary. Disclosed so no one mistakes it for a product dep.

## Sequence (one continuous run, no hand steps after invoke)
    apt-get install curl ca-certificates gnupg lsb-release python3 python3-pip sudo
    cp -r /src /tmp/aegis-src && cd /tmp/aegis-src
    bash install.sh                          # Steps 1-9
    pip3 install fastapi uvicorn python-multipart   # app deps
    python3 backend/main.py                  # start app from /opt/aegis
    POST /api/sessions/start?lab_id=lab-04-two-as-peering&student_name=Selina

## Result
    INSTALL EXIT = 0  (Steps 1-9 ran; Docker + ContainerLab from scratch)
    Install record /opt/aegis/assets/installed-image-id.txt written:
        installed_layers_sha256=bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
    App: FastAPI started, /api/labs returned the 8 discovered labs.
    Deploy: session 8b1d0677 — r1..r6 all running
            (clab-aegis-two-as-peering-8b1d0677-*).

## Digest cited ON THE COLD HOST (the exit-bar assertion)
    POST /api/sessions/8b1d0677/submit?node=r1
      -> grade.runtime_digest = sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c

    Independent reads + the pin all agree:
      running container .Image (docker inspect)  -> sha256:acb8d8dcd72a44c3389184bc168ee61444072566afaa59704eb1aa27250027b8
      layer chain of that image                  -> sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
      /opt/aegis/assets/installed-image-id.txt   -> installed_layers_sha256=bb7ef23a...     == MATCH
      assets/frr-image.pin layers_sha256         -> bb7ef23a...                             == MATCH
      grade.runtime_digest                       -> bb7ef23a...                             == MATCH

## Honest note on an earlier None this hour
A prior composite attempt (session 20490067, same host method) resolved the
topology and the digest off the running container correctly, but the grade call
returned runtime_digest=None. That was a race: the grade fired before the
session's substrate resolution settled. Re-run (8b1d0677) graded cleanly with
the digest present. No code change was made; the resolution path was not
defective, the ordering was. Flagging it because a flaky digest-on-first-grade
would be a real product bug if it recurs — see NEXT below.

## Exit-bar status
    cold-host install.sh landing current digest ........ DONE (this run + 2026-09-19 bare-metal run)
    prototype running against a real topology .......... DONE (this run + 2026-09-20 step-3 proof)
    digest pasted and recorded ......................... DONE (this file; pin; installed-image-id.txt)

## NEXT (smallest real item)
    Chase the first-grade race: after /sessions/start, a submit immediately
    after can read runtime_digest=None before resolution settles. Make
    resolution eager at start (or have submit resolve-on-demand) so the FIRST
    grade always cites the digest. Small, contained, and it hardens step 5.

## Not touched: ethan's lab containers. Session 8b1d0677 stopped -> destroyed.
