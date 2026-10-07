FIX — the README's only deploy command pointed at a lab we do NOT ship
Date: 2026-09-27 ~23:20 EDT   By: Selina   Trigger: hourly cron run 27

WHY: 26 runs verified the labs WORK. Nobody had verified they are INSTALLABLE /
that the deploy story matches the ship order - and "get the software deployed"
is Dad's second ask. Read the shipped README.md as an operator would.

DEFECT FOUND (real, operator-facing):
  README "## Running a Lab" gave exactly one deploy + one destroy command:
     sudo containerlab deploy --topo lab-definitions/demo-01-two-pcs-and-a-switch.yml
  That file EXISTS but it is NOT one of our two shipping labs. Our LAB-A is
  srl-demo-unsolved/demo-01-two-pcs-and-a-real-switch-unsolved.yml.
  Worse: the README never named either shipping lab at all -
     'demo-01-two-pcs-and-a-real-switch-unsolved' -> 0 hits
     'demo-02-two-switches-one-router-unsolved'   -> 0 hits
     'srl-demo-unsolved' / 'srl-demo2-unsolved'   -> 0 hits
  and "Lab topologies: lab-definitions/*.yml" implies all of them ship, when the
  order is ship exactly TWO.
  => An operator following the README one-handed would deploy the WRONG lab and
     have no idea our two labs exist. A deploy-story defect, not a code bug.

FIX (reversible; docs only): rewrote "## Running a Lab" and added a
"## The Shipping Labs" table naming BOTH labs with their exact topology + grader
paths, stated "ships exactly two", and noted that normal operation does not need
manual containerlab commands (the server deploys/destroys per session).
Backup: README.md.bak-2026-09-27-shiplabs

VERIFIED AFTER:
  every path the corrected README names exists (2 topologies + 2 graders) - OK
  README now names demo-01 (3 hits) and demo-02 (1 hit)
  both topology files parse and match the graders: demo-01 name=aegis-demo-01-srl-switch
    nodes=3 ; demo-02 name=aegis-demo-02-srl-two-switch-router nodes=5
  containerlab present (the documented command is runnable)

STATE: 0 clab containers, service active, /api 200.
NOT COMPLETE. Dad's word alone.
