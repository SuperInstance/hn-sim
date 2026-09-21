#!/usr/bin/env python3
"""Generate the held-out persona set and lock it with a hash commitment.

DESIGN LAW 3: the held-out set exists for resistance through unknowability.
It is generated ONCE by the operator (seed never committed), its SHA-256
manifest is committed as heldout/manifest.sha256, and the persona files
themselves stay out of the tree (heldout/personas/ is gitignored).

Usage:
    HNSIM_HELDOUT_SEED=<operator-secret> python tools/generate_heldout.py

Tests pin: manifest well-formedness, hash-match of locally present files,
and that no dev/test code path loads heldout/personas without the env unlock.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "heldout" / "personas"
MANIFEST = REPO_ROOT / "heldout" / "manifest.sha256"
N_HELD_OUT = 4

# Held-out stances are deliberately different from the six dev personas.
# They are generated as skeletons — the operator fleshes them out before
# any evaluation. v0 ships the commitment + the generation protocol.
HELDOUT_STANCE_SEEDS = [
    ("heldout_foss_purist", "Only votes for GPL-compatible code with a COPYING file. Reads licenses for sport."),
    ("heldout_stats_pedant", "Checks every number for a confidence interval. Rates READMEs by their error bars."),
    ("heldout_vc_brain", "Pattern-matches every Show HN against a12z's last twenty portfolio companies."),
    ("heldout_contrarian", "Upvotes precisely what the current thread consensus hates. Cannot be predicted by design."),
]


def generate(seed: str, out_dir: Path = OUT_DIR, n: int = N_HELD_OUT) -> dict[str, str]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: dict[str, str] = {}
    for pid, stance in HELDOUT_STANCE_SEEDS[:n]:
        persona = {
            "id": pid,
            "name": pid.replace("heldout_", "").replace("_", " ").title(),
            "stance": stance,
            "reach_scale": round(rng.uniform(0.5, 1.5), 2),
            "variants": [
                {
                    "id": f"{pid}-v{i}",
                    "note": f"held-out variant {i} (operator-fleshed)",
                    "base_propensity": round(rng.uniform(0.25, 0.45), 2),
                    "trigger_patterns": [
                        {"pattern": r"\w+", "weight": 0.1, "label": "placeholder — flesh out before eval"}
                    ],
                    "kill_phrase_patterns": [],
                    "comment_templates": ["[held-out: operator writes this]"],
                    "kill_comment_template": "[held-out: operator writes this]",
                    "verdict_phrase_up": "held",
                    "verdict_phrase_down": "held",
                }
                for i in range(3)
            ],
            "missing_advice": [],
            "_heldout": True,
        }
        path = out_dir / f"{pid}.json"
        payload = json.dumps(persona, indent=2, sort_keys=True).encode()
        path.write_bytes(payload)
        entries[pid] = hashlib.sha256(payload).hexdigest()
    lines = [f"{digest}  {pid}.json" for pid, digest in sorted(entries.items())]
    lines.append("")
    MANIFEST.write_text(
        "# held-out persona commitment (SHA-256). Files live OUTSIDE the tree.\n"
        "# Regenerate only via tools/generate_heldout.py with the operator seed.\n"
        + "\n".join(lines),
        encoding="utf-8",
    )
    return entries


def main() -> int:
    seed = os.environ.get("HNSIM_HELDOUT_SEED")
    if not seed:
        print("error: HNSIM_HELDOUT_SEED not set. The seed is never committed.", file=sys.stderr)
        return 2
    entries = generate(seed)
    print(f"wrote {len(entries)} held-out personas -> {OUT_DIR}")
    print(f"commitment -> {MANIFEST}")
    for pid, digest in sorted(entries.items()):
        print(f"  {digest}  {pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
