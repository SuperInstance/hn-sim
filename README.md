# hn-sim

**Goodhart-resistant HN reception forecast compass. Distribution, not scalar. Persona rotation + held-out resistance. Never a gate.**

`hn-sim` forecasts how a Show HN would be received — before you post it — by
running a set of written personas against your repo's surface (README, title,
Show-HN draft). It runs entirely on inference: no network, no real Hacker News.

## Usage

```bash
pip install -e .
hn-sim forecast --repo . --title "Show HN: penrose — deterministic Penrose floor simulator" --rotate
hn-sim forecast --repo . --title "..." --show-hn drafts/post.md --json --seed 42
```

## The five design laws

These are Casey doctrine (2026-09-20 17:12). They are load-bearing. A change
that violates one is a bug, not a feature.

### 1. The forecast is NEVER a scalar

Output = an **upvote-count distribution** (bucket probabilities over stochastic
samples) **+ argued comments per persona**. A single number — mean, median,
"expected upvotes," score — is forbidden by design.

Why: a scalar is the **Performed-Twist trap**. When a room knows the exact
probe it will be measured against, it rehearses the surprise-recovery routine
for that probe. Every Goodhart catastrophe starts as a single number someone
decided to optimize. A distribution keeps the uncertainty in view; you cannot
gradient-ascent a histogram without confronting its tail.

### 2. Persona set: six, written as data files

`personas/` holds six persona files — `skeptic`, `front_page_regular`,
`security_reader`, `maker`, `tired_dev`, `domain_expert` — each with name,
stance, trigger patterns, kill-phrase patterns, and comment templates. They are
the audience. The engine is just their attention.

### 3. Persona rotation + a held-out set

Each forecast run samples **K≥2 variants per persona stance** (`--rotate`, on
by the Red Queen principle: the probe must change faster than the room can
rehearse against it). Each persona ships ≥3 variants with different trigger
phrasings and sensitivities.

Additionally, a **held-out persona set** is generated and locked with a
**SHA-256 hash commitment** (`heldout/manifest.sha256`). The held-out files
live outside the tree; the seed is never committed. No development or test
path loads them (`HNSIM_HELDOUT=1` is the only unlock, reserved for
evaluation). This is resistance through **unknowability**: you cannot tune for
an audience you cannot read.

### 4. The sim is a COMPASS, never a release gate

The CLI advises — *"what would make this land better,"* with argued reasons
per persona. It does not pass, fail, score, or block. Exit code is 0 on every
successful forecast. If you find yourself wanting a threshold out of hn-sim,
that want is the bug.

### 5. Simulation on inference only

Input is the repo surface: README + title + optional Show-HN draft (+ optional
first-screen doc). No network calls, no real HN scraping, ever. A test
pinning this monkeypatches `socket` to explode; the forecast must still run.

## The Goodhart-resistance argument

> When a measure becomes a target, it ceases to be a measure.

An HN-score predictor that outputs one number will be optimized until the
number is high and the post is dead. hn-sim resists on four axes:

1. **No scalar to climb** (Law 1) — the output is a distribution; optimizing
   its shape honestly means improving the actual surface, because…
2. **The probe rotates** (Law 3) — every run samples different persona
   variants, so surface tweaks that game one probe configuration don't
   generalize; the development process never sees a constant target.
3. **The audience is partly unknowable** (Law 3, held-out set) — a locked,
   unreadable persona set waits in evaluation. Tuning for the six visible
   personas is allowed; it will be checked against ones you never saw.
4. **The tool refuses to be a gate** (Law 4) — by never emitting pass/fail,
   hn-sim removes the incentive to sandbag the measurement.

## Compass, not gate — the operational law

`hn-sim forecast` answers one question: *what would make this land better?*
Each persona's advice block is a direction, not a verdict. A forecast that
says "0–10 with 60%" is not a failure — it is a compass needle pointing at
the empty demo section. Follow it or don't; the tool will not judge you,
because a tool that judges you is a tool you will learn to fool.

## Development

```bash
python -m pytest          # 18 tests pinning the five laws
```

Layout:

```
hn_sim/            engine (surface, personas, forecaster, cli)
personas/          the six dev personas (data files)
heldout/           manifest.sha256 commitment; personas/ is gitignored
tools/             held-out generator (operator-seeded, seed never committed)
tests/             law-pinning tests
```

## License

MIT.
