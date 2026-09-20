"""Forecaster core: distribution samples + argued comments per persona.

DESIGN LAW 1: the forecast is NEVER a scalar. Output is an upvote-count
DISTRIBUTION (bucket probabilities over stochastic samples) plus argued
comments. Any single number — mean, median, expected value — is forbidden
by design and absent from the output schema.

DESIGN LAW 4: this is a COMPASS. The output advises what would make the
surface land better, with argued reasons. It never passes, fails, scores,
or gates anything.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .personas import Persona, TriggerHit, Variant
from .surface import Surface

# Canonical buckets. Widths grow because HN reception is log-scale in nature.
BUCKETS: list[tuple[int, int, str]] = [
    (0, 10, "0-10"),
    (10, 50, "10-50"),
    (50, 200, "50-200"),
    (200, 800, "200-800"),
    (800, 10**9, "800+"),
]
N_SAMPLES_DEFAULT = 400
ROTATION_K_DEFAULT = 2

# HN attention is a lottery: even perfect reception draws a random reach.
# Log-normal prior => median story ~30 upvotes, honest 800+ tail.
REACH_MU = 3.4
REACH_SIGMA = 0.95


@dataclass
class PersonaReport:
    persona_id: str
    persona_name: str
    stance: str
    variant_ids: list[str]
    killed: bool
    comments: list[dict] = field(default_factory=list)
    evidence_count: int = 0
    advice: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "persona_id": self.persona_id,
            "persona_name": self.persona_name,
            "stance": self.stance,
            "variant_ids": self.variant_ids,
            "killed": self.killed,
            "comments": self.comments,
            "advice": self.advice,
        }


@dataclass
class Forecast:
    """The forecast. NOTE: there is deliberately no score/mean/expected field."""

    title: str
    insufficient_surface: bool
    distribution: dict[str, float]
    n_samples: int
    seed: int
    rotation_k: int
    personas: list[PersonaReport]
    honest_note: str | None = None

    COMPASS_HEADER = "COMPASS, NOT A GATE — hn-sim advises; it never passes or fails."

    def to_dict(self) -> dict:
        d = {
            "compass_not_gate": True,
            "title": self.title,
            "insufficient_surface": self.insufficient_surface,
            "distribution": self.distribution,
            "n_samples": self.n_samples,
            "seed": self.seed,
            "rotation_k": self.rotation_k,
            "personas": [p.to_dict() for p in self.personas],
        }
        if self.honest_note:
            d["honest_note"] = self.honest_note
        return d


def _flat_distribution() -> dict[str, float]:
    p = 1.0 / len(BUCKETS)
    return {label: p for _, _, label in BUCKETS}


def _reaction(evidence: list[TriggerHit], base: float) -> float:
    r = base + sum(h.weight for h in evidence)
    return min(1.0, max(0.02, r))


def _bucket_of(count: float) -> str:
    c = max(0.0, count)
    for lo, hi, label in BUCKETS:
        if lo <= c < hi:
            return label
    return BUCKETS[-1][2]


def _render_comment(
    template: str,
    hits: list[TriggerHit],
    variant: Variant,
    up: bool,
    rng: random.Random,
    extra: dict | None = None,
) -> dict:
    hit = max(hits, key=lambda h: abs(h.weight)) if hits else None
    quote = hit.quote if hit else "…"
    section = hit.section if hit else "(whole surface)"
    file = hit.file if hit else "README.md"
    label = hit.label if hit else "general impression"
    text = template.format(
        file=file,
        section=section,
        quote=quote,
        label=label,
        label_cap=label[:1].upper() + label[1:],
        verdict_phrase=variant.verdict_phrase_up if up else variant.verdict_phrase_down,
        verdict_phrase_cap=(variant.verdict_phrase_up if up else variant.verdict_phrase_down)[:1].upper()
        + (variant.verdict_phrase_up if up else variant.verdict_phrase_down)[1:],
        **(extra or {}),
    )
    citations = (
        [{"file": h.file, "section": h.section, "quote": h.quote, "pattern": h.pattern, "label": h.label} for h in hits[:3]]
        if hits
        else []
    )
    return {"persona_variant": variant.id, "text": text, "citations": citations}


def forecast(
    surface: Surface,
    personas: list[Persona],
    selection: dict[str, list[Variant]],
    seed: int,
    n_samples: int = N_SAMPLES_DEFAULT,
    rotation_k: int = ROTATION_K_DEFAULT,
) -> Forecast:
    rng = random.Random(seed)

    if surface.is_empty or not any(d.text.strip() for d in surface.docs):
        note = (
            "Insufficient surface: README (and any Show-HN draft) is empty or missing. "
            "The honest forecast is no forecast — the distribution below is maximum-ignorance, "
            "not a prediction. Write the README, then forecast again."
        )
        reports = [
            PersonaReport(
                persona_id=p.id,
                persona_name=p.name,
                stance=p.stance,
                variant_ids=[v.id for v in selection[p.id]],
                killed=False,
                comments=[],
                advice=_advice_for(p, surface, None),
            )
            for p in personas
        ]
        return Forecast(
            title=surface.title,
            insufficient_surface=True,
            distribution=_flat_distribution(),
            n_samples=n_samples,
            seed=seed,
            rotation_k=rotation_k,
            personas=reports,
            honest_note=note,
        )

    # ---- per-variant probing
    per_variant: list[tuple[Persona, Variant, list[TriggerHit], list[TriggerHit]]] = []
    for p in personas:
        for v in selection[p.id]:
            evidence, kills = v.matches(surface)
            per_variant.append((p, v, evidence, kills))

    # ---- distribution samples (the ONLY quantitative output shape)
    counts = {label: 0 for _, _, label in BUCKETS}
    weights: list[float] = []
    reactors: list[tuple[Persona, Variant, list[TriggerHit], bool]] = []
    for p, v, evidence, kills in per_variant:
        killed = len(kills) > 0
        r = _reaction(evidence, v.base_propensity) * (0.15 if killed else 1.0)
        w = max(0.01, r * p.reach_scale)
        weights.append(w)
        reactors.append((p, v, evidence, killed))
    total_w = sum(weights)
    for _ in range(n_samples):
        # pick a persona-variant proportional to weighted reaction
        pick = rng.random() * total_w
        acc = 0.0
        idx = 0
        for i, w in enumerate(weights):
            acc += w
            if pick <= acc:
                idx = i
                break
        p, v, evidence, killed = reactors[idx]
        r = _reaction(evidence, v.base_propensity) * (0.15 if killed else 1.0)
        reach = math.exp(rng.gauss(REACH_MU, REACH_SIGMA))
        upvotes = reach * (r**2) * p.reach_scale * (1.0 + 0.2 * len(evidence))
        counts[_bucket_of(upvotes)] += 1
    distribution = {label: counts[label] / n_samples for _, _, label in BUCKETS}

    # ---- argued comments: 2-3 per active persona, each citing its triggers
    reports: list[PersonaReport] = []
    for p in personas:
        variants = selection[p.id]
        all_evidence: list[TriggerHit] = []
        any_killed = False
        for v in variants:
            evidence, kills = v.matches(surface)
            all_evidence.extend(evidence)
            any_killed = any_killed or len(kills) > 0
        all_evidence.sort(key=lambda h: -abs(h.weight))
        n_comments = min(3, max(2, len(all_evidence))) if all_evidence else (1 if any_killed else 0)
        comments: list[dict] = []
        if any_killed and variants:
            kill_hits: list[TriggerHit] = []
            for v in variants:
                _, kills = v.matches(surface)
                kill_hits.extend(kills)
            comments.append(
                {
                    "persona_variant": variants[0].id,
                    "text": variants[0].kill_comment_template,
                    "citations": [
                        {"file": h.file, "section": h.section, "quote": h.quote, "pattern": h.pattern, "label": "kill phrase"}
                        for h in kill_hits[:3]
                    ],
                }
            )
        if n_comments and variants:
            avg_r = sum(_reaction([h for h in all_evidence if True], v.base_propensity) for v in variants) / len(variants)
            up = avg_r >= 0.45
            templates = rng.sample(variants[0].comment_templates, min(len(variants[0].comment_templates), n_comments))
            extra = {}
            for key in ("five_word_verdict_up", "five_word_verdict_down"):
                if key in variants[0].extra:
                    extra["five_word_verdict"] = (
                        variants[0].extra["five_word_verdict_up"] if up else variants[0].extra["five_word_verdict_down"]
                    )
            for i, tpl in enumerate(templates):
                hits = [all_evidence[i]] if i < len(all_evidence) else (all_evidence[:1] if all_evidence else [])
                comments.append(_render_comment(tpl, hits, variants[0], up, rng, extra))
        comments = comments[:3]
        reports.append(
            PersonaReport(
                persona_id=p.id,
                persona_name=p.name,
                stance=p.stance,
                variant_ids=[v.id for v in variants],
                killed=any_killed,
                comments=comments,
                evidence_count=len(all_evidence),
                advice=_advice_for(p, surface, all_evidence),
            )
        )

    return Forecast(
        title=surface.title,
        insufficient_surface=False,
        distribution=distribution,
        n_samples=n_samples,
        seed=seed,
        rotation_k=rotation_k,
        personas=reports,
    )


def _advice_for(p: Persona, surface: Surface, evidence: list[TriggerHit] | None) -> list[str]:
    """Compass advice: what would make this land better, per persona. Never a verdict."""
    text = surface.all_text().lower()
    out: list[str] = []
    for entry in p.missing_advice:
        pats = entry.get("if_absent", [])
        if all(not _loose_match(pat, text) for pat in pats):
            out.append(entry["advice"])
    return out


def _loose_match(pat: str, text: str) -> bool:
    import re

    try:
        return re.search(pat, text, re.IGNORECASE) is not None
    except re.error:
        return pat.lower() in text
