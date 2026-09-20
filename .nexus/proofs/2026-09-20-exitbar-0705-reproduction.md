# Proof — EXIT BAR reproduced independently (5th run) + ledger reconciliation

Date: 2026-09-20 07:05 EDT (hour 07:00 nexus cron)
Driver: Selina
Status: EXIT BAR MET — reproduced live this hour by execution, not by reading the ledger.

## Why this hour
STATUS.md hours 00:0x–06:0x claim steps 1-5 done, composite done, exit bar
reproduced 4x. Cron RULES: verify, don't trust the ledger. This hour re-verified
the physical artifacts and reproduced the live deploy path. No features added.

## Static + artifact verification (executed)
    bash -n install.sh                -> CLEAN
    python3 -m py_compile main.py     -> CLEAN
    on-disk Dockerfile.frr sha256     = cce15a8696ae045e8001f2b32107b1261fa7fc5ba30ad4cab5dfa8c7bc8f38cf
    aegis/frr:latest label            = cce15a86...8f38cf   MATCH (gate will skip rebuild — correct)
    running-container layer chain     = bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
      (computed with install.sh's EXACT framing: {{range .RootFS.Layers}}{{.}} {{end}}
       | tr -d ' ' -> printf '%s' | sha256sum)
    assets/frr-image.pin layers_sha256 = bb7ef23a...   MATCH
    assets/frr-image.pin tarball sha256 = 9c6837d2...  == actual tarball sha   MATCH
    tarball manifest.json Config       = blobs/sha256/acb8d8dc... (the pinned image) RepoTags aegis/frr:latest

## A false alarm I raised and then disproved (recorded so it isn't mistaken for a defect)
    My first layer-chain computation used `{{range .RootFS.Layers}}{{.}}{{"\n"}}{{end}}`
    (newline-joined) and produced 70c6f4fe... / 2771bd56... — MISMATCH vs pin.
    Root cause: MY framing, not the product. install.sh joins with a literal
    space and strips spaces; same bytes, different separator => different hash.
    Using install.sh's own form yields bb7ef23a... == pin. No product defect.
    (Same class of bug the ledger documents at 21:0x/22:xx. Verified before
    claiming anything broken — consistent with "no fake red" as well as green.)

## Live end-to-end reproduction (executed this hour)
    App already UP on :8000. POST /api/sessions/start?lab_id=lab-04-two-as-peering
      -> session a11fe90a, r1..r6 up (isolated session-unique copy:
         clab-aegis-two-as-peering-a11fe90a-*)
      -> lab-04 metadata.grader = grader_lab_04_two_as_peering (resolved, module exists,
         import OK, callable grade)
    FIRST grade, node r3, fired immediately:
        passed=false score=0.35
        runtime_digest = sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
        feedback in lab-04's OWN vocabulary ("wrong-session carry test",
        "which AS 65001 must originate") => the REAL module ran, not _fallback_grade.
    STOP -> {"status":"destroyed"}; 0 session containers remain.

## Exit-bar assertions (all met, re-verified)
    cold-host install.sh lands the current digest, no hand steps .... DONE (bare-metal runs 2026-09-19; composite 2026-09-20; pin+tarball+label consistent now)
    prototype running against a real topology ...................... session a11fe90a, Ethan's lab-04 topology file, isolated copy
    digest pasted and recorded ..................................... bb7ef23a... above; in pin; in installed-image-id.txt
    a state cannot be cited without its digest ..................... FIRST grade carried it (race fix holds)

## Ledger reconciliation
    The older 03:0x proof file still says "lab-04 grader still does not exist".
    STALE: grader_lab_04_two_as_peering.py exists (shipped 2026-09-20 05:08,
    after that proof). Verified this hour by import + live dispatch.

## Not touched
    Ethan's lab clab-aegis-two-as-peering-d7776359-r1..r6 — 6 containers still Up.
    His other running clab-* sets (tier-*, capstone) untouched.

## Remaining open product work (NOT exit-bar blockers)
    - optional GraderResult refused/error in-band discriminator.
    - cosmetic SyntaxWarning in grader_neteng_capstone.py.
    - project not under version control (cron notes this; still true — `git` reports
      not-a-repo despite git being installed).

==> NEXUS is a finished deployed product by the stated exit definition. The
    NEXUS-HOURLY-DRIVE cron is retireable.
