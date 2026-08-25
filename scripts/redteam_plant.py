"""A credential-shaped value drawn against the properties the DETECTOR keys on.

Two drills plant one: `security_scan_redteam.sh` (M9-S9, in a working-tree file
and in a commit) and `hook_redteam.sh` (M9-S13, in the index). They must not each
carry their own generator — F-071 is the record of what goes wrong when the plant
is drawn carelessly, and a lesson learned in one copy is a lesson the other copy
has not learned.

WHY IT IS GENERATED AT ALL. A drill carrying a credential-shaped LITERAL becomes
a finding in the scan it exists to test; the first version of the audit's own
record tripped `generic-api-key` thirteen times on its own sha256 fields and was
right to.

WHY IT IS DRAWN AGAINST THE RULES (F-071). The first version was flaky — roughly
two runs in five reported all six detection checks failing, i.e. "the scanner
found nothing", which is exactly the sentence these drills exist to stop anyone
believing. Flaky in the direction that reads as good news. Two causes, both about
the plant and neither about the scan:

  * `generic-api-key` matches `[\\w.=-]`, which does NOT include `+` or `/`. A
    base64 alphabet puts those anywhere, and one early in the string truncates the
    match below the rule's minimum length. So: alphanumeric only.
  * both rules carry an entropy floor, and a short random string clears it only on
    average. So the draw RETRIES until it does, and the entropy it settled on is
    PRINTED — a property a future reader can see rather than infer.

Entropy is measured over the WHOLE matched string, prefix included: that is what
the scanner sees, and measuring the random part alone would set the floor on a
quantity nobody keys on.

Usage (stdout, three lines: key id, secret, "<h_id> <h_secret>"):
    python3 scripts/redteam_plant.py
"""

from __future__ import annotations

import collections
import math
import secrets
import string

ALNUM_UPPER = string.ascii_uppercase + string.digits
ALNUM = string.ascii_letters + string.digits


def shannon(value: str) -> float:
    counts = collections.Counter(value)
    n = len(value)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def draw(alphabet: str, length: int, floor: float, prefix: str = "") -> tuple[str, float]:
    for _ in range(10_000):
        candidate = prefix + "".join(secrets.choice(alphabet) for _ in range(length))
        if (h := shannon(candidate)) >= floor:
            return candidate, h
    raise SystemExit("could not draw a high-entropy plant; the floors are wrong")


def aws_pair() -> tuple[str, str, float, float]:
    key_id, h_id = draw(ALNUM_UPPER, 16, 3.6, prefix="AKIA")
    secret, h_secret = draw(ALNUM, 40, 4.8)
    return key_id, secret, h_id, h_secret


if __name__ == "__main__":
    key_id, secret, h_id, h_secret = aws_pair()
    print(key_id)
    print(secret)
    print(f"{h_id:.3f} {h_secret:.3f}")
