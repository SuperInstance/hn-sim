"""hn-sim CLI.

    hn-sim forecast --repo . --title "Show HN: ..." [--show-hn draft.md]
                    [--rotate] [--seed N] [--json] [--samples N]

DESIGN LAW 4: the CLI advises — "what would make this land better" — it does
not pass/fail. Exit code is 0 on every successful forecast.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from . import __version__
from .forecaster import BUCKETS, N_SAMPLES_DEFAULT, ROTATION_K_DEFAULT, Forecast, forecast
from .personas import PersonaError, canonical_variants, load_personas, rotate_variants
from .surface import load_surface

BAR_WIDTH = 24


def _bar(p: float, width: int = BAR_WIDTH) -> str:
    n = int(round(p * width))
    return "█" * n + "·" * (width - n)


def render_text(f: Forecast) -> str:
    lines: list[str] = []
    lines.append(f.COMPASS_HEADER)
    lines.append(f"title: {f.title!r}")
    lines.append("")
    if f.honest_note:
        lines.append(f"NOTE: {f.honest_note}")
        lines.append("")
    lines.append(f"distribution ({f.n_samples} samples, seed={f.seed}, rotation K={f.rotation_k}):")
    for _, _, label in BUCKETS:
        p = f.distribution.get(label, 0.0)
        lines.append(f"  {label:>7}  {_bar(p)}  {p*100:5.1f}%")
    lines.append("")
    lines.append("(no scalar summary exists by design — DESIGN LAW 1)")
    lines.append("")
    for pr in f.personas:
        lines.append(f"--- {pr.persona_name} [variants: {', '.join(pr.variant_ids)}]{ ' [KILL PHRASE]' if pr.killed else ''}")
        if not pr.comments and f.insufficient_surface:
            lines.append("  (no signal to argue from — see note above)")
        for c in pr.comments:
            lines.append(f"  «{c['text']}»")
            for cit in c["citations"]:
                lines.append(f"      ↳ triggered by {cit['file']} §{cit['section']} — \"{cit['quote'][:90]}\"")
        for a in pr.advice:
            lines.append(f"  ➜ would land better if: {a}")
        lines.append("")
    lines.append("This forecast is a compass for development direction, never a release gate.")
    return "\n".join(lines)


def cmd_forecast(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"error: --repo {repo} is not a directory", file=sys.stderr)
        return 2
    try:
        surface = load_surface(repo, title=args.title, show_hn_draft=Path(args.show_hn) if args.show_hn else None)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        personas = load_personas(Path(args.personas_dir))
    except PersonaError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**31)
    rng = random.Random(seed)
    if args.rotate:
        selection = rotate_variants(personas, k=args.k, rng=rng)
        rotation_k = args.k
    else:
        selection = canonical_variants(personas)
        rotation_k = 1

    f = forecast(
        surface,
        personas,
        selection,
        seed=seed,
        n_samples=args.samples,
        rotation_k=rotation_k,
    )
    if args.json:
        print(json.dumps(f.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_text(f))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hn-sim",
        description="Goodhart-resistant HN reception forecast compass. Distribution, not scalar. Never a gate.",
    )
    p.add_argument("--version", action="version", version=f"hn-sim {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    fc = sub.add_parser("forecast", help="forecast reception of a repo surface (inference only, no network)")
    fc.add_argument("--repo", default=".", help="path to the repo surface lives in (default: .)")
    fc.add_argument("--title", required=True, help='the HN title, e.g. "Show HN: thing — what it does"')
    fc.add_argument("--show-hn", dest="show_hn", default=None, help="path to Show-HN draft markdown")
    fc.add_argument("--rotate", action="store_true", help="rotate persona variants (K>=2 per stance) — the default probe is constant; rotation defeats it")
    fc.add_argument("--k", type=int, default=ROTATION_K_DEFAULT, help="variants sampled per persona under --rotate (default 2)")
    fc.add_argument("--seed", type=int, default=None, help="RNG seed for reproducibility")
    fc.add_argument("--samples", type=int, default=N_SAMPLES_DEFAULT, help="distribution sample count (default 400)")
    fc.add_argument("--json", action="store_true", help="machine-readable output")
    fc.add_argument("--personas-dir", default="personas", help="persona data directory (default: ./personas)")
    fc.set_defaults(func=cmd_forecast)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
