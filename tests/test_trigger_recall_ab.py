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
BASELINE_COVERAGE_SHARE = 0.25
BASELINE_POSTS_WITH_EVIDENCE = {
    "domain_expert": 2,
    "front_page_regular": 8,
    "maker": 4,
    "security_reader": 4,
    "skeptic": 1,
    "tired_dev": 4,
}


def test_fixture_identity() -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256


def test_recall_baseline() -> None:
    report = run(FIXTURE)
    assert report["sample_size"] == 40
    assert report["coverage_any_persona"]["share"] == BASELINE_COVERAGE_SHARE
    assert report["coverage_any_persona"]["posts"] == 10
    got = {pid: s["posts_with_evidence"] for pid, s in report["per_persona"].items()}
    assert got == BASELINE_POSTS_WITH_EVIDENCE


def test_no_kill_phrase_fires_on_real_posts() -> None:
    # Baseline fact, pinned: zero kill-phrase hits on the sample. If a persona
    # edit starts killing real posts, that is a behavior change worth a human.
    assert run(FIXTURE)["kill_coverage"]["posts"] == 0


def test_no_generic_triggers() -> None:
    # Goodhart tripwire: a trigger firing on >50% of the sample carries no
    # information. Baseline: none. Keep it none.
    assert run(FIXTURE)["generic_triggers_over_half"] == {}
