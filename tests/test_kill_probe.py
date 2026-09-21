"""Kill-phrase capability probe — SYNTHETIC known-bad fixture (NOT HN data).

The real 40-post Show-HN sample has 0 kill firings, honestly reported as
"untested-not-proven": legitimate posts cannot demonstrate the kill mechanism
works. This probe asks the narrower liveness question with hand-authored
synthetic posts (tests/fixtures/synthetic_known_bad.json, provenance inside):

1. CAPABILITY: every designed-bad post is killed by >=1 persona variant —
   the kill mechanism is live in all six personas.
2. PRECISION: the two well-evidenced synthetic posts are NOT killed.
3. LITERALISM (pinned finding): the paraphrase post ("another take", "a
   small layer over") is NOT killed — kill phrases match verbatim today.
   That is a known limit, pinned so it surfaces instead of eroding silently.

Replace the fixture with a real flagged/removed Show-HN sample when one is
obtainable, then re-pin the hashes below and say why in the PR.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.trigger_recall_ab import run  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "synthetic_known_bad.json"
FIXTURE_SHA256 = "32ce66b4af05dd06efbfb5ef284fa1a7dbbd439bcf4a6f38a9829d99ae976afc"

DESIGNED_BAD = {
    "syn-bad-01-wrapper",
    "syn-bad-02-secret-sauce",
    "syn-bad-03-trust-us",
    "syn-bad-04-military-grade",
    "syn-bad-05-rocket-emoji",
    "syn-bad-06-fast-paced",
    "syn-bad-07-magic",
    "syn-bad-08-synergy",
    "syn-bad-09-demo-soon",
    "syn-bad-10-poc",
    "syn-bad-11-orders-of-magnitude",
}
MUST_SURVIVE = {
    "syn-good-01-evidenced-maker",
    "syn-good-02-evidenced-domain",
    "syn-edge-01-paraphrase",  # paraphrase: literal-mechanism pin, see docstring
}

# Measured 2026-09-21 on the fixture above: all six personas land >=1 kill,
# kill coverage 11/14 (only designed-bad posts die), no generic triggers.
EXPECTED_KILL_HITS_TOTAL = {
    "domain_expert": 7,
    "front_page_regular": 8,
    "maker": 8,
    "security_reader": 7,
    "skeptic": 7,
    "tired_dev": 4,
}


def _fixture_posts() -> dict[str, dict]:
    import json

    data = json.loads(FIXTURE.read_text())
    return {p["objectID"]: p for p in data["posts"]}


def test_fixture_identity() -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256


def test_provenance_labels_fixture_synthetic() -> None:
    data = __import__("json").loads(FIXTURE.read_text())
    origin = data["provenance"]["origin"]
    assert "SYNTHETIC" in origin and "NOT HN data" in origin


def test_every_designed_bad_post_is_killed() -> None:
    report = run(FIXTURE)
    killed = _killed_post_ids()
    assert DESIGNED_BAD <= killed, f"kill mechanism silent on: {DESIGNED_BAD - killed}"


def test_evidenced_and_paraphrase_posts_survive() -> None:
    killed = _killed_post_ids()
    assert not (MUST_SURVIVE & killed), f"false kills: {MUST_SURVIVE & killed}"


def test_kill_coverage_is_exactly_the_designed_bad_set() -> None:
    report = run(FIXTURE)
    assert report["sample_size"] == 14
    assert report["kill_coverage"]["posts"] == len(DESIGNED_BAD)
    assert report["kill_coverage"]["share"] == round(len(DESIGNED_BAD) / 14, 3)
    assert _killed_post_ids() == DESIGNED_BAD


def test_all_six_personas_can_kill() -> None:
    report = run(FIXTURE)
    got = {pid: s["kill_hits_total"] for pid, s in report["per_persona"].items()}
    assert got == EXPECTED_KILL_HITS_TOTAL
    assert all(c > 0 for c in got.values())


def test_no_generic_trigger_on_probe_sample() -> None:
    report = run(FIXTURE)
    assert report["generic_triggers_over_half"] == {}


def _killed_post_ids() -> set[str]:
    import json

    sys_path_before = sys.path[:]
    try:
        from hn_sim.personas import load_personas
        from tools.trigger_recall_ab import post_surface

        personas = load_personas(REPO_ROOT / "personas", allow_heldout=False)
        killed: set[str] = set()
        for p in _fixture_posts().values():
            surface = post_surface(p)
            for persona in personas:
                for variant in persona.variants:
                    _, kills = variant.matches(surface)
                    if kills:
                        killed.add(p["objectID"])
        return killed
    finally:
        sys.path[:] = sys_path_before
