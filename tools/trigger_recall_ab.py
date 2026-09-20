"""Trigger-recall A/B: dev persona triggers vs a vendored real Show-HN sample.

DESIGN LAW 5 holds: the forecaster never touches the network. This is a
dev-time calibration tool; its input is a vendored fixture with provenance
(tests/fixtures/show_hn_sample.json), and its output is a report for humans
plus a pinned summary the test suite guards against trigger drift.

Question answered: when real Show-HN posts (not our hand-written drafts) are
shown to the six dev personas, which triggers fire, how often, and which
patterns are so generic they fire on everything (Goodhart tripwire: a trigger
that fires on >50% of posts carries no information).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hn_sim.personas import load_personas
from hn_sim.surface import Surface, SurfaceDoc

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "show_hn_sample.json"
GENERIC_THRESHOLD = 0.5  # a trigger firing on more than half the sample is noise


def post_surface(post: dict) -> Surface:
    text = post.get("selftext") or ""
    return Surface(title=post.get("title") or "", docs=[SurfaceDoc(file="show_hn_post.md", text=text)])


def run(fixture: Path = FIXTURE) -> dict:
    data = json.loads(fixture.read_text())
    posts = data["posts"]
    personas = load_personas(Path(__file__).resolve().parent.parent / "personas", allow_heldout=False)

    per_persona: dict[str, dict] = {}
    trigger_fires: Counter = Counter()
    covered_posts: set[str] = set()
    kill_posts: set[str] = set()

    for persona in personas:
        evidence_posts = 0
        kill_hits = 0
        evidence_total = 0
        for post in posts:
            surface = post_surface(post)
            hit_any = False
            for variant in persona.variants:
                evidence, kills = variant.matches(surface)
                if evidence:
                    hit_any = True
                    evidence_total += len(evidence)
                    for h in evidence:
                        trigger_fires[f"{persona.id}:{h.pattern}"] += 1
                if kills:
                    kill_hits += len(kills)
                    kill_posts.add(post["objectID"])
            if hit_any:
                evidence_posts += 1
                covered_posts.add(post["objectID"])
        per_persona[persona.id] = {
            "posts_with_evidence": evidence_posts,
            "evidence_hits_total": evidence_total,
            "kill_hits_total": kill_hits,
        }

    n = len(posts)
    generic = {
        pat: c for pat, c in trigger_fires.items() if c / n > GENERIC_THRESHOLD
    }
    top_triggers = [
        {"trigger": pat, "posts": c, "share": round(c / n, 3)}
        for pat, c in trigger_fires.most_common(10)
    ]
    return {
        "sample_size": n,
        "posts_with_selftext": sum(1 for p in posts if p.get("selftext")),
        "coverage_any_persona": {
            "posts": len(covered_posts),
            "share": round(len(covered_posts) / n, 3),
        },
        "kill_coverage": {"posts": len(kill_posts), "share": round(len(kill_posts) / n, 3)},
        "per_persona": per_persona,
        "top_triggers": top_triggers,
        "generic_triggers_over_half": generic,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", type=Path, default=FIXTURE)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    report = run(args.fixture)
    if args.json:
        print(json.dumps(report, indent=1, sort_keys=True))
        return
    print(f"sample: {report['sample_size']} real Show-HN posts "
          f"({report['posts_with_selftext']} with selftext)")
    cov = report["coverage_any_persona"]
    print(f"any persona evidence: {cov['posts']}/{report['sample_size']} ({cov['share']})")
    kill = report["kill_coverage"]
    print(f"any kill phrase: {kill['posts']}/{report['sample_size']} ({kill['share']})")
    print("\nper persona (posts with >=1 evidence hit / total evidence / kills):")
    for pid, s in sorted(report["per_persona"].items()):
        print(f"  {pid:20s} {s['posts_with_evidence']:3d}  {s['evidence_hits_total']:4d}  {s['kill_hits_total']:3d}")
    print("\ntop triggers (pattern -> posts fired on):")
    for t in report["top_triggers"]:
        print(f"  {t['share']:5.1%}  {t['trigger']}")
    if report["generic_triggers_over_half"]:
        print("\nGENERIC (fire on >50% of sample — carry no information):")
        for pat, c in sorted(report["generic_triggers_over_half"].items()):
            print(f"  {c/report['sample_size']:5.1%}  {pat}")
    else:
        print("\nno generic triggers over the 50% tripwire")


if __name__ == "__main__":
    main()
