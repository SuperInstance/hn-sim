"""Persona loading, variant rotation, trigger matching, and the held-out lock.

DESIGN LAW 2: personas are data files — name, stance, trigger patterns, kill phrases.
DESIGN LAW 3: rotation samples K>=2 variants per persona stance per run; the held-out
set is locked behind a hash commitment and refuses to load during development.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from .surface import Surface

SCHEMA_VERSION = 1
HELDOUT_ENV_VAR = "HNSIM_HELDOUT"


class PersonaError(Exception):
    pass


@dataclass
class TriggerHit:
    pattern: str
    label: str
    weight: float
    file: str
    section: str
    quote: str


@dataclass
class Variant:
    id: str
    note: str
    base_propensity: float
    trigger_patterns: list[dict]
    kill_phrase_patterns: list[str]
    comment_templates: list[str]
    kill_comment_template: str
    verdict_phrase_up: str
    verdict_phrase_down: str
    extra: dict = field(default_factory=dict)

    def matches(self, surface: Surface) -> tuple[list[TriggerHit], list[TriggerHit]]:
        """Return (evidence_hits, kill_hits) against the surface."""
        evidence: list[TriggerHit] = []
        kills: list[TriggerHit] = []
        for doc in surface.docs:
            for t in self.trigger_patterns:
                rx = re.compile(t["pattern"], re.IGNORECASE)
                for m in rx.finditer(doc.text):
                    section = doc.section_for_offset(m.start())
                    quote = _quote(doc.text, m.start(), m.end())
                    evidence.append(
                        TriggerHit(
                            pattern=t["pattern"],
                            label=t["label"],
                            weight=float(t["weight"]),
                            file=doc.file,
                            section=section,
                            quote=quote,
                        )
                    )
        for doc in surface.docs:
            for kp in self.kill_phrase_patterns:
                rx = re.compile(kp, re.IGNORECASE)
                for m in rx.finditer(doc.text):
                    kills.append(
                        TriggerHit(
                            pattern=kp,
                            label="kill phrase",
                            weight=0.0,
                            file=doc.file,
                            section=doc.section_for_offset(m.start()),
                            quote=_quote(doc.text, m.start(), m.end()),
                        )
                    )
        return evidence, kills


@dataclass
class Persona:
    id: str
    name: str
    stance: str
    reach_scale: float
    variants: list[Variant]
    missing_advice: list[dict]
    source_path: Path

    def __post_init__(self) -> None:
        if len(self.variants) < 2:
            raise PersonaError(
                f"persona {self.id}: DESIGN LAW 3 requires >=2 variants per stance, found {len(self.variants)}"
            )


def _quote(text: str, start: int, end: int, radius: int = 60) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    snippet = text[lo:hi].replace("\n", " ").strip()
    return snippet if len(snippet) <= 140 else snippet[:137] + "..."


def _variant_from_raw(raw: dict) -> Variant:
    return Variant(
        id=raw["id"],
        note=raw.get("note", ""),
        base_propensity=float(raw["base_propensity"]),
        trigger_patterns=raw["trigger_patterns"],
        kill_phrase_patterns=raw.get("kill_phrase_patterns", []),
        comment_templates=raw["comment_templates"],
        kill_comment_template=raw.get("kill_comment_template", "Kill phrase matched. Pass."),
        verdict_phrase_up=raw.get("verdict_phrase_up", "upvoted"),
        verdict_phrase_down=raw.get("verdict_phrase_down", "not upvoted"),
        extra={k: v for k, v in raw.items() if k not in {
            "id", "note", "base_propensity", "trigger_patterns", "kill_phrase_patterns",
            "comment_templates", "kill_comment_template", "verdict_phrase_up", "verdict_phrase_down",
        }},
    )


def load_personas(personas_dir: Path, allow_heldout: bool = False) -> list[Persona]:
    """Load persona data files. Refuses held-out personas unless explicitly unlocked.

    The held-out set is the resistance-through-unknowability mechanism (DESIGN LAW 3):
    it is generated, hash-committed in heldout/manifest.sha256, and never loaded by
    any development or test path.
    """
    personas_dir = personas_dir.resolve()
    if not allow_heldout and os.environ.get(HELDOUT_ENV_VAR) != "1":
        if "heldout" in personas_dir.parts:
            raise PersonaError(
                f"refusing to load held-out personas from {personas_dir}: "
                f"{HELDOUT_ENV_VAR}=1 not set. The held-out set is never touched during development."
            )
    files = sorted(personas_dir.glob("*.json"))
    if not files:
        raise PersonaError(f"no persona files in {personas_dir}")
    out: list[Persona] = []
    for f in files:
        raw = json.loads(f.read_text(encoding="utf-8"))
        _validate_persona_raw(raw, f)
        out.append(
            Persona(
                id=raw["id"],
                name=raw["name"],
                stance=raw["stance"],
                reach_scale=float(raw.get("reach_scale", 1.0)),
                variants=[_variant_from_raw(v) for v in raw["variants"]],
                missing_advice=raw.get("missing_advice", []),
                source_path=f,
            )
        )
    return out


def _validate_persona_raw(raw: dict, f: Path) -> None:
    for key in ("id", "name", "stance", "variants"):
        if key not in raw:
            raise PersonaError(f"{f.name}: missing key {key!r}")
    for v in raw["variants"]:
        for key in ("id", "base_propensity", "trigger_patterns", "comment_templates"):
            if key not in v:
                raise PersonaError(f"{f.name}: variant missing {key!r}")
        for t in v["trigger_patterns"]:
            re.compile(t["pattern"])  # raises on bad regex


def rotate_variants(personas: list[Persona], k: int, rng: random.Random) -> dict[str, list[Variant]]:
    """DESIGN LAW 3: sample K>=2 variants per persona stance (probe rotation).

    Every forecast run probes with a different combination, so development cannot
    rehearse against a constant probe (the Performed-Twist trap).
    """
    if k < 2:
        raise PersonaError(f"rotation requires K>=2, got {k}")
    selection: dict[str, list[Variant]] = {}
    for p in personas:
        take = min(k, len(p.variants))
        selection[p.id] = rng.sample(p.variants, take)
    return selection


def canonical_variants(personas: list[Persona]) -> dict[str, list[Variant]]:
    """Non-rotated mode: first variant per persona. --rotate switches to sampling."""
    return {p.id: [p.variants[0]] for p in personas}


# ---------------------------------------------------------------- held-out lock

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_heldout_manifest(repo_root: Path) -> dict[str, str]:
    """Read heldout/manifest.sha256 -> {persona_id: sha256}."""
    manifest = repo_root / "heldout" / "manifest.sha256"
    if not manifest.is_file():
        raise PersonaError("heldout/manifest.sha256 missing")
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise PersonaError(f"manifest malformed digest for {name!r}")
        entries[Path(name).stem] = digest
    return entries


def heldout_files_match_manifest(repo_root: Path) -> bool:
    """True iff locally-present held-out personas hash-match the commitment."""
    entries = verify_heldout_manifest(repo_root)
    d = repo_root / "heldout" / "personas"
    present = {p.stem: p for p in d.glob("*.json")} if d.is_dir() else {}
    for pid, digest in entries.items():
        if pid not in present:
            return False
        if sha256_file(present[pid]) != digest:
            return False
    return True
