"""Pins for the trigger-recall A/B calibration (real Show-HN sample vs dev personas).

The numbers below are the calibration baseline from docs/trigger-recall-ab.md.
If a persona trigger file changes, this test fails on purpose: either the
change is intended (re-baseline the pins with the tool and say why in the PR)
or it is silent trigger drift (revert).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.trigger_recall_ab import run  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "show_hn_sample.json"

# Vendored sample identity — a changed fixture is a different experiment.
FIXTURE_SHA256 = "e1a3f59d06f2bab223108a806aba9924224550e6eb832a887982f87a0b48902a"

# Baseline measured 2026-09-21 on the fixture above (see docs/trigger-recall-ab.md).
# Recalibration #1 (2026-09-21): title added as a first-class evidence doc in
# the A/B harness (28/40 real posts are title-only — selftext-only matching
# made receipt-checkers deaf by construction) and skeptic/domain_expert
# patterns recalibrated to the genre. front_page_regular's tautological
# "Show HN" trigger removed (tripped the generic tripwire once titles matched).
# Pins below are the DELIBERATELY re-based recalibration numbers.
# Recalibration #2 (2026-09-21): skeptic's access-claim trigger split — bare
# "free" moved to a weaker price-claim trigger with ad-free/ad free excluded
# (it misfired on price-free/ad-free titles; A1Lab was a pure misfire post,
# so skeptic evidence posts drop 12→11; coverage_any_persona unchanged at 24).
BASELINE_COVERAGE_SHARE = 0.6
BASELINE_POSTS_WITH_EVIDENCE = {
    "domain_expert": 10,
    "front_page_regular": 8,
    "maker": 7,
    "security_reader": 7,
    "skeptic": 11,
    "tired_dev": 5,
}


def test_fixture_identity() -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256


def test_recall_baseline() -> None:
    report = run(FIXTURE)
    assert report["sample_size"] == 40
    assert report["coverage_any_persona"]["share"] == BASELINE_COVERAGE_SHARE
    assert report["coverage_any_persona"]["posts"] == 24
    got = {pid: s["posts_with_evidence"] for pid, s in report["per_persona"].items()}
    assert got == BASELINE_POSTS_WITH_EVIDENCE


def test_top_trigger_counts_posts_not_hits() -> None:
    # Recalibration #3 (2026-09-21): the report's top_triggers/gate counted
    # evidence HITS, not distinct posts. "I (built|made|wrote|hacked)" read
    # 8/40 = 20% when it actually touches 6/40 = 15% (Ifso and the Mac
    # window switcher each carry two first-person hits). The generic-tripwire
    # semantic is "fires on >50% of POSTS" — now computed that way.
    report = run(FIXTURE)
    top = report["top_triggers"][0]
    assert top["trigger"] == "front_page_regular:I (built|made|wrote|hacked)"
    assert top["posts"] == 6
    assert top["hits"] == 8
    assert top["share"] == 0.15
    # Per-firing read (all 6 genuine first-person maker claims):
    #   Bailout ("i made bailout for a pretty specific problem"),
    #   Judge Jev ("I made this little game"), A1Lab ("I built A1Lab"),
    #   Human Benchmark (title: "so I built it"), Ifso (x2, one dogfooding
    #   narrative "if I made some key financial decisions"), Mac switcher
    #   (x2). No misfire on the sample — this was a measurement fix, not a
    #   persona recalibration.
    assert all("posts" in t and "hits" in t for t in report["top_triggers"])
    assert report["generic_triggers_over_half"] == {}


def test_no_kill_phrase_fires_on_real_posts() -> None:
    # Baseline fact, pinned: zero kill-phrase hits on the sample. If a persona
    # edit starts killing real posts, that is a behavior change worth a human.
    assert run(FIXTURE)["kill_coverage"]["posts"] == 0


def test_blind_spot_map() -> None:
    # Blind-spot map (shipped 2026-09-21, see docs/blind-spots.md): the 16
    # posts no persona fires any evidence on. Headline finding: ALL 16 are
    # title-only — every post with selftext is covered after recalibrations
    # #1-#3. The remaining blindness is structural (thin surface), not
    # persona stance. The with_selftext==0 invariant is the real pin: if a
    # selftext-bearing post ever lands in the blind list, persona drift made
    # the receipt-checkers deaf again and this test must fail loudly.
    report = run(FIXTURE)
    blind = report["blind_spots"]
    assert blind["posts"] == 16
    assert blind["title_only"] == 16
    assert blind["with_selftext"] == 0
    assert len(blind["entries"]) == 16
    assert all(not e["has_selftext"] for e in blind["entries"])
    covered = report["coverage_any_persona"]["posts"]
    assert covered + blind["posts"] == report["sample_size"]


def test_no_generic_triggers() -> None:
    # Goodhart tripwire: a trigger firing on >50% of the sample carries no
    # information. Baseline: none. Keep it none.
    assert run(FIXTURE)["generic_triggers_over_half"] == {}


def test_access_claim_split() -> None:
    # Recalibration #2 (2026-09-21): skeptic's access-claim trigger used to
    # include bare "free", which misfired on price-free and ad-free claims
    # ("Ad free Learning platform", "a free subscription tracker" —
    # price/adjacency claims, not access claims). The trigger was split:
    #   access claim  = open[- ]?source | no sign ?up | no account  (w 0.10)
    #   price claim   = free, with "ad free"/"ad-free" excluded   (w 0.06)
    # Verified against the real pinned sample: 3 of the 7 posts the old
    # combined trigger fired on were non-access uses of "free".
    import json
    import re

    posts = json.loads(FIXTURE.read_text())["posts"]
    access = re.compile(r"\b(?:open[- ]?source|no sign ?up|no account)\b", re.I)
    price = re.compile(r"(?<!ad[- ])\bfree\b", re.I)

    def text_of(p: dict) -> str:
        return " ".join([p.get("title") or "", p.get("selftext") or ""])

    ad_free_posts = [p for p in posts if re.search(r"ad[- ]free", text_of(p), re.I)]
    assert ad_free_posts, "expected the ad-free Show-HN post in the pinned sample"
    for p in ad_free_posts:
        assert not access.search(text_of(p)), (
            "access-claim trigger must not fire on ad-free claims: "
            + (p.get("title") or "")
        )
        assert price.search(text_of(p)) is None, (
            "price trigger must also exclude ad-free claims: " + (p.get("title") or "")
        )

    # And the split must not weaken genuine access claims on the sample.
    genuine = [p for p in posts if access.search(text_of(p))]
    assert len(genuine) == 4, f"expected 4 genuine access-claim posts, got {len(genuine)}"
