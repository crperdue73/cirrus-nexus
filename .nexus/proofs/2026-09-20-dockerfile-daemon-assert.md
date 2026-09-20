# 2026-09-20 18:0x EDT — Dockerfile.frr daemon sed now asserts itself

Step: last hour's named NEXT item (`STATUS.md` 17:2x): "make the Dockerfile sed
assert itself (fail the build if a daemon pattern didn't match)".

## Defect (silent, same class as the stale-digest bug)

`Dockerfile.frr` did:
    sed -i -e 's/zebra=no/zebra=yes/' \
           -e 's/ospfd=yes/ospfd=no/' \
           -e 's/bgpd=yes/bgpd=no/' \
           -e 's/staticd=no/staticd=yes/' /etc/frr/daemons

On the pinned substrate (FRR 10.5.3 / Alpine) `/etc/frr/daemons` contains NO
`zebra=` or `staticd=` lines at all — verified live:

    $ docker run --rm aegis/frr:latest grep -nE '^(zebra|staticd)=' /etc/frr/daemons
    (no output)

The file's own header states "watchfrr, zebra and staticd are always started."
So two of the four substitutions matched nothing and were pure no-ops. The image
*looks* configured (the Dockerfile reads as if it enables zebra/staticd) while
the build asserted nothing. A sed that silently matches nothing is exactly how a
wrong substrate ships unnoticed — the same failure mode as the stale digest
gate: the mechanism that was supposed to prove something proved nothing.

## Fix (Dockerfile.frr)

- Stop sed-ing on patterns that may not exist.
- Disable only what we intend to disable, with one pattern:
      sed -i -E 's/^(ospfd|bgpd)=.*/\1=no/' "$f"
- Then ASSERT the intended daemon state. Every required pattern must be present
  after the write, or the BUILD FAILS:
      require() { grep -qE "^$1=$2$" "$f" || { echo "BUILD ASSERT FAILED..."; \
                  grep -nE "^$1=" "$f"; exit 1; }; }
      require ospfd no
      require bgpd no
  A disabled daemon is asserted too, so a future FRR that flips a default cannot
  silently re-enable bgpd/ospfd.
- No image tag/pin moved: the pinned image id/layer chain is UNCHANGED (this is a
  build-gate hardening, not a substrate change). aegis/frr:latest untouched.

## Verification (executed, both directions — no fake green)

POSITIVE — correct Dockerfile builds, assert passes:
    $ docker build -f Dockerfile.frr -t aegis/frr:assert-test .
    #6 0.173 FRR daemon state asserted: ospfd=no bgpd=no (zebra+staticd always-on)
    #9 writing image sha256:dfa9aa94... done ; EXIT 0

NEGATIVE — wrong required pattern HARD-FAILS the build:
    $ sed 's/require bgpd no;/require bgpd yes;/' Dockerfile.frr > Dockerfile.neg
    $ docker build -f Dockerfile.neg -t aegis/frr:assert-neg .
    #6 BUILD ASSERT FAILED: expected ^bgpd=yes$ in /etc/frr/daemons
    #6 17:bgpd=no
    ERROR: ... did not complete successfully: exit code: 1
  The assert fires, names the expected pattern, and echoes the offending line.

Cleaned up: both test tags removed; /tmp/assert-neg deleted.
`aegis/frr:latest` not rebuilt/retagged — pin unchanged; Ethan's containers
untouched.

## Artifact

- Dockerfile.frr (edited on disk, committed).
- This proof.

## Status

STATUS.md 17:2x NEXT list item #1 CLOSED. Item #2 remains: ship a SECOND image
tag with bgpd enabled so BGP labs become deployable rather than correctly
refused (lab-04 currently refuses on `requires_daemons: [bgpd]`).
Not touched: Ethan's lab containers.
