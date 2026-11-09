# CANARY (2026-11-09): a grader module that exists and imports cleanly but exposes
# no EXPECTED / node->IP map for the lint to read. Exists only to exercise the
# NO-EXPECTED row. Deliberately has no grade() logic worth running.
def grade(session):
    return {"passed": False, "detail": "canary: exposes no expectation map"}
