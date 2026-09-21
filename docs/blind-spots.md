# Blind-spot map — the posts the compass cannot see

Shipped 2026-09-21 on top of recalibration #3 (hit-vs-post-counting).

The trigger-recall A/B report counts what the six dev personas *can* see.
This doc is the honest other half: what they **cannot** see, per post, and
whether that blindness is a defect or just thin evidence.

## Headline finding

**All 16 blind posts are title-only.** After recalibrations #1–#3
(title-as-evidence-doc; skeptic/domain_expert genre recal; access/price
split; post-based counting), every one of the 12 sample posts that carries a
selftext fires at least one persona's evidence triggers. The remaining blind
field is **structural, not stance**: a title that states what the thing is,
without any receipt-checkable claim (no "I built", no "open source", no
"offline", no "free"), gives every persona exactly nothing to cite.

Invariant pinned by `test_blind_spot_map`: `with_selftext == 0`. If a
selftext-bearing post ever lands in the blind list again, that means persona
drift re-deafened the receipt-checkers — the test fails on purpose.

## The blind 16 (vendored sample, sha256 pinned in tests)

| objectID | title |
|---|---|
| 49776507 | Jev Slop Filter for X and LinkedIn |
| 49776523 | A competition for small neural networks that play strategy games |
| 49776570 | I got Claude Code and Codex to argue about my code |
| 49776813 | Simple Mass Downloader – Bulk Download Files in Chrome |
| 49777643 | TypeFerry – Typed RPC, real-time data, and React from one contract |
| 49777691 | Jev filters large HN discussions |
| 49777820 | MidiSlayer, a desktop sight-reading trainer for MIDI keyboards |
| 49778087 | Scrolling Text Generator – marquee, ticker and credits in the browser |
| 49778137 | TetherPHP – a small PHP framework designed for agents and humans |
| 49778185 | I inadvertently built an English to Bash transpiler |
| 49778358 | System One Harness (SOH), the harness for System One models |
| 49778923 | Agentic OS: one Rust Linux binary, one SQLite and sandbox per actor |
| 49778966 | NiceTryGPT and CTF and riduzione degli shortcut LLM |
| 49779155 | Emetgate – a verification gate between an LLM and your source tree |
| 49779362 | A browser MMO designed to be played by scripts, not people |
| 49779400 | Roffume – Add fragrance to your resume with roff |

## Classification of the blindness

- **Genre-blind (most):** titles that only name the artifact
  ("MidiSlayer, a desktop sight-reading trainer") with no first-person
  maker claim, no license claim, no access claim. There is genuinely nothing
  to receipt-check on the surface we model. A real HN reader clicks through
  to the repo; DESIGN LAW 5 says we don't. That gap is the forecaster's
  `insufficient_surface` honest-negative path, not a persona defect.
- **Near-miss pattern:** "I got Claude Code and Codex to argue about my code"
  and "I inadvertently built an English to Bash transpiler" carry
  first-person maker energy, but the pinned maker trigger is the literal
  `I (built|made|wrote|hacked)` — "got ... to argue" and "inadvertently
  built" are paraphrases. This is the literalism pin from the kill-probe
  recurring on the evidence side: the mechanism is literal today.
  Extending the maker trigger to `I (?:also )?\w+ (?:an?\s+\w+)?(built|made)`
  style coverage is a candidate for recalibration #4 — with the tripwire
  check that it must not cross 50% post-share.

## Honest caveats

- Blind ≠ the post fails on HN. Several of these titles are exactly the
  plain-descriptive style that does fine. The map measures persona coverage,
  not reception quality.
- The sample is 40 posts, sha-pinned; blind membership is a function of the
  fixture AND the personas. New sample → re-pin (the test forces it).
- The forecaster's job for a blind post is `insufficient_surface` — say the
  surface is too thin to argue from, never invent evidence.
