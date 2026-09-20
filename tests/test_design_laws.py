"""Tests pinning the design laws of hn-sim v0."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from hn_sim.forecaster import BUCKETS, forecast  # noqa: E402
from hn_sim.personas import (  # noqa: E402
    PersonaError,
    canonical_variants,
    heldout_files_match_manifest,
    load_personas,
    rotate_variants,
    verify_heldout_manifest,
)
from hn_sim.surface import Surface, SurfaceDoc  # noqa: E402

PERSONAS_DIR = REPO_ROOT / "personas"

GOOD_README = """# Show HN: penrose — deterministic Penrose floor simulator

tl;dr: a zero-dependency Python simulator for Penrose tilings with a seeded
dice engine; `pip install penrose-floor` and you are running in one minute.

## Demo
Live demo: https://penrose.example.com — 30-second asciinema inside.

## What it is
A single-file simulator that renders Penrose rhomb tilings from a seeded RNG.

## Evaluation
Benchmarked against `quilt-studio` kernels; methodology in BENCHMARKS.md; n=200
seeds, reproducible via `make bench`. Baseline comparisons included.

## Security
No telemetry. Local-first. Works offline. Reproducible build; SBOM shipped.

## Known limitations
Only rhombic tilings; kite-and-dart not implemented yet.

MIT license. CI green. 214 tests.
"""

MARKETING_README = """# 🚀 Revolutionize your workflow with AI-powered synergistic synergy

We're excited to announce the future of work. In today's fast-paced world,
unlock the power of our proprietary algorithm. Just trust us.

Join our waitlist! Discord: discord.gg/example
"""


@pytest.fixture(scope="module")
def personas():
    return load_personas(PERSONAS_DIR)


def _surface(title: str, readme: str | None):
    docs = [] if readme is None else [SurfaceDoc(file="README.md", text=readme)]
    return Surface(title=title, docs=docs)


# ---------------------------------------------------------------- DESIGN LAW 1
# The forecast is NEVER a scalar.


def _all_keys(obj) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        keys |= {str(k).lower() for k in obj}
        for v in obj.values():
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


def test_distribution_not_scalar(personas):
    sel = canonical_variants(personas)
    f = forecast(_surface("Show HN: x", GOOD_README), personas, sel, seed=7)
    d = f.to_dict()
    assert "distribution" in d
    banned = re.compile(r"score|expected|mean|median|rating|^verdict$|grade|points")
    leaks = [k for k in _all_keys(d) if banned.search(k)]
    assert leaks == [], f"scalar leak in keys: {leaks}"
    assert set(d["distribution"].keys()) == {label for _, _, label in BUCKETS}


def test_distribution_buckets_sum_to_one(personas):
    sel = canonical_variants(personas)
    f = forecast(_surface("Show HN: x", GOOD_README), personas, sel, seed=11)
    total = sum(f.distribution.values())
    assert abs(total - 1.0) < 1e-9


def test_no_scalar_anywhere_in_json_output(personas, tmp_path, capsys=None):
    # belt-and-braces: run the CLI in --json mode and regex-hunt for scalar fields
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(GOOD_README)
    out = subprocess.run(
        [sys.executable, "-m", "hn_sim.cli", "forecast", "--repo", str(repo),
         "--title", "Show HN: x", "--json", "--seed", "3"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert out.returncode == 0
    payload = json.loads(out.stdout)
    assert isinstance(payload["distribution"], dict)
    scalar_keys = [k for k in _all_keys(payload) if re.search(r"score|expected|mean|median|grade", k, re.I)]
    assert scalar_keys == []


# ---------------------------------------------------------------- DESIGN LAW 2
# Persona set: 6 data files, each with name, stance, trigger + kill patterns.


def test_six_persona_files_validate(personas):
    files = sorted(PERSONAS_DIR.glob("*.json"))
    assert len(files) == 6
    ids = {p.id for p in personas}
    assert ids == {
        "skeptic", "front_page_regular", "security_reader",
        "maker", "tired_dev", "domain_expert",
    }
    for p in personas:
        assert p.name and p.stance
        for v in p.variants:
            assert v.trigger_patterns and v.kill_phrase_patterns is not None
            assert len(v.comment_templates) >= 2


# ---------------------------------------------------------------- DESIGN LAW 3
# Rotation K>=2; held-out set locked behind a hash commitment.


def test_rotation_samples_k_at_least_2(personas):
    import random

    sel = rotate_variants(personas, k=2, rng=random.Random(42))
    for pid, variants in sel.items():
        assert len(variants) >= 2, f"{pid} rotated with <2 variants"
        ids = [v.id for v in variants]
        assert len(set(ids)) == len(ids), f"{pid} duplicated variants in one rotation"


def test_rotation_changes_probes_across_seeds(personas):
    import random

    a = rotate_variants(personas, k=2, rng=random.Random(1))
    b = rotate_variants(personas, k=2, rng=random.Random(999))
    diffs = sum(1 for pid in a if {v.id for v in a[pid]} != {v.id for v in b[pid]})
    assert diffs >= 1, "rotation never changes the probe — Performed-Twist trap is open"


def test_heldout_manifest_locked():
    entries = verify_heldout_manifest(REPO_ROOT)
    assert len(entries) == 4
    assert heldout_files_match_manifest(REPO_ROOT)


def test_heldout_refuses_to_load_by_default():
    with pytest.raises(PersonaError):
        load_personas(REPO_ROOT / "heldout" / "personas")


def test_heldout_never_in_dev_personas(personas):
    entries = verify_heldout_manifest(REPO_ROOT)
    dev_ids = {p.id for p in personas}
    assert dev_ids.isdisjoint(entries.keys())


# ---------------------------------------------------------------- DESIGN LAW 4
# Compass, not gate. Honest CLI. Exit 0. No pass/fail vocabulary.


def test_trigger_citations_present(personas):
    sel = canonical_variants(personas)
    f = forecast(_surface("Show HN: x", GOOD_README), personas, sel, seed=5)
    for pr in f.personas:
        for c in pr.comments:
            assert c["citations"], f"{pr.persona_name} comment without citation"
            for cit in c["citations"]:
                assert cit["file"] and cit["section"] and cit["quote"]
                assert cit["quote"] in GOOD_README.replace("\n", " ") or len(cit["quote"]) > 20


def test_comments_are_argued(personas):
    sel = canonical_variants(personas)
    f = forecast(_surface("Show HN: x", GOOD_README), personas, sel, seed=5)
    for pr in f.personas:
        for c in pr.comments:
            assert len(c["text"]) > 40, f"{pr.persona_name} comment not argued"


def test_kill_phrase_suppresses_and_switches_voice(personas):
    sel = canonical_variants(personas)
    f = forecast(_surface("Show HN: hype", MARKETING_README), personas, sel, seed=9)
    fpr = next(pr for pr in f.personas if pr.persona_id == "front_page_regular")
    assert fpr.killed
    assert any("Rocket emoji" in c["text"] or "🚀" in cit["quote"] for c in fpr.comments for cit in c["citations"])


def test_compass_advice_present_and_reasoned(personas):
    sel = canonical_variants(personas)
    f = forecast(_surface("Show HN: x", GOOD_README), personas, sel, seed=5)
    assert any(pr.advice for pr in f.personas), "compass gave no advice"
    for pr in f.personas:
        for a in pr.advice:
            assert len(a) > 30


def test_cli_never_gate_exit_zero(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(GOOD_README)
    out = subprocess.run(
        [sys.executable, "-m", "hn_sim.cli", "forecast", "--repo", str(repo),
         "--title", "Show HN: x", "--rotate", "--seed", "8"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert out.returncode == 0
    assert "COMPASS, NOT A GATE" in out.stdout
    assert "distribution" in out.stdout
    assert not re.search(r"\bPASS\b", out.stdout)
    assert not re.search(r"\bFAIL\b", out.stdout)
    assert not re.search(r"score\s*[:=]", out.stdout)


# ---------------------------------------------------------------- DESIGN LAW 5
# Inference only: no network, ever.


def test_no_network(monkeypatch, personas):
    def _boom(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "__init__", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    sel = canonical_variants(personas)
    f = forecast(_surface("Show HN: x", GOOD_README), personas, sel, seed=13)
    assert abs(sum(f.distribution.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------- honesty
# Empty surface => honest negative, maximum-ignorance distribution.


def test_honest_negative_when_surface_empty(personas):
    sel = canonical_variants(personas)
    f = forecast(_surface("", ""), personas, sel, seed=1)
    assert f.insufficient_surface
    assert f.honest_note and "Insufficient surface" in f.honest_note
    # maximum-ignorance: flat over buckets
    for p in f.distribution.values():
        assert abs(p - 1.0 / len(BUCKETS)) < 1e-9
    # no invented comments
    assert all(pr.comments == [] for pr in f.personas)
    # but the compass still advises
    assert any(pr.advice for pr in f.personas)


def test_deterministic_same_seed(personas):
    sel = canonical_variants(personas)
    a = forecast(_surface("Show HN: x", GOOD_README), personas, sel, seed=99)
    b = forecast(_surface("Show HN: x", GOOD_README), personas, sel, seed=99)
    assert a.distribution == b.distribution
    assert [c["text"] for pr in a.personas for c in pr.comments] == [
        c["text"] for pr in b.personas for c in pr.comments
    ]


def test_different_surfaces_differ(personas):
    sel = canonical_variants(personas)
    good = forecast(_surface("Show HN: x", GOOD_README), personas, sel, seed=99)
    bad = forecast(_surface("Show HN: hype", MARKETING_README), personas, sel, seed=99)
    assert good.distribution != bad.distribution
