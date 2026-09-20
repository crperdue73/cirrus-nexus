# Proof — EXIT BAR independently reproduced (this hour)

Date: 2026-09-20 ~03:0x EDT (hour 03:00 nexus cron)
Driver: Selina
Status: EXIT BAR MET — reproduced cold, end-to-end, this hour. Cron is retireable.

## Why this hour
Steps 1-5 + composite were all marked done in STATUS.md. The cron RULES say
verify, don't trust the ledger ("NEVER claim a step is done that you did not
do... No fake green"). So this hour did not add features — it REPRODUCED the
exit bar from scratch on a bare host, and recorded the raw transcript.

## Host
    docker run --rm --privileged -v <aegis-project>:/src:ro debian:12 bash <script>
    BARE BEFORE: docker=NONE  containerlab=NONE   (printed by the harness)
    Harness-only: storage-driver=vfs (nested docker can't mount overlay2).
    NOT a product dependency; disclosed.

## Sequence (one continuous run, no hand steps after invoke)
    apt deps -> bash install.sh (Steps 1-9) -> pip app deps ->
    python3 /opt/aegis/backend/main.py -> POST /sessions/start ->
    POST /sessions/<id>/submit?node=r1 -> stop

## Raw result (from /tmp/nexus-full.log)
    INSTALL EXIT=0
    Step 7: Loading pinned FRR image from aegis-frr-image.tar.gz...
            FRR image loaded and verified against pin
            verified on Dockerfile fingerprint cce15a8696ae045e... and
            layer-chain bb7ef23a07dcb6c6...
    installed-image-id.txt:
        installed_local_image_id=sha256:acb8d8dc...
        installed_dockerfile_sha256=cce15a8696ae045e8001f2b32107b1261fa7fc5ba30ad4cab5dfa8c7bc8f38cf
        installed_layers_sha256=bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
    LABS  HTTP=200
    START HTTP=200  -> session 479bac5f (lab-04-two-as-peering, Ethan's topology file)
    GRADE HTTP=200  -> grade.runtime_digest =
        sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
    STOP  HTTP=200

## Exit-bar assertions
    cold-host install.sh lands the current digest, no hand steps .... MATCH
       (installed_layers_sha256 == assets/frr-image.pin layers_sha256)
    prototype running against a real topology ...................... session 479bac5f, lab-04
    digest pasted and recorded ..................................... above
    a state cannot be cited without its digest ..................... first grade carried it

## Independent reads agree
    running-container .Image (docker inspect)  -> sha256:acb8d8dc... (daemon-local id)
    layer chain of that image                  -> sha256:bb7ef23a... (transport identity)
    /opt/aegis/assets/installed-image-id.txt   -> bb7ef23a...        MATCH
    assets/frr-image.pin layers_sha256         -> bb7ef23a...        MATCH
    grade.runtime_digest                       -> bb7ef23a...        MATCH

## Not touched
    Ethan's lab containers (clab-aegis-two-as-peering-d7776359-*, and the other
    running clab-* sets) were not modified. This run used an isolated
    session-unique copy inside its own container.

## Honest caveats (unchanged, narrow)
    - Target must have apt (stock debian:12 does). Non-apt distros out of scope.
    - lab-04 grader module (grader_lab_04_two_as_peering) still does not exist;
      grading runs through the digest-guarded fallback. Real competency grading
      for lab-04 remains open product work (not part of the exit bar).
    - daemon-local id differs across hosts by design; the pin key is the
      layer-chain (transport-invariant). Correct, documented in the pin.
