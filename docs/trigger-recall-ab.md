# Trigger-Recall A/B — dev personas vs real Show-HN posts

**Date:** 2026-09-21 · **Status:** calibration baseline, pinned by `tests/test_trigger_recall_ab.py`
**Tool:** `python3 tools/trigger_recall_ab.py` · **Fixture:** `tests/fixtures/show_hn_sample.json`

## Why

Lane AD's honest gap: persona triggers were written against our own hand-written
Show-HN drafts. Hand-written drafts contain the vocabulary the author already
knows matters. Real posts don't. This A/B measures what the six dev personas
actually do when shown real Show-HN posts, so the compass is calibrated against
the world, not against our mirror.

Design law 5 holds: the forecaster never touches the network. The sample is a
vendored dev-time fixture (40 most-recent Show-HN posts at fetch time, Algolia
`search_by_date?tags=show_hn`), sha256-pinned in the test. Re-fetching is a new
experiment with a new pin, never a silent refresh.

## Method

Each post becomes a `Surface(title, [show_hn_post.md])` — selftext when present,
title-only otherwise. Every dev persona (held-out set stays locked) runs every
variant's trigger patterns against every post. Count: posts with ≥1 evidence
hit, per-trigger fire counts, kill-phrase hits, and a Goodhart tripwire (any
trigger firing on >50% of the sample is generic noise).

## Results (recalibration #1, 2026-09-21)

Two deliberate method changes, pins re-based (test fails on silent drift, so
any future change to these numbers must say why):

1. **The title is now a first-class evidence doc** (`show_hn_title.md`). The
   baseline matched selftext only — and 28/40 real Show-HN posts have no
   selftext. Receipt-checkers (skeptic, domain_expert) were near-deaf *by
   construction*, not by stance. On HN the title IS the pitch; the harness
   now reads it.
2. **front_page_regular's `Show HN` trigger removed** — tautological in a
   Show-HN-only sample (tripped the >50% generic tripwire the moment titles
   were matched: zero information, it fired on every post twice).
3. **skeptic + domain_expert patterns recalibrated to the genre** from the
   fired-quote list: skeptic gains counted-scale (`on 5,500 CLINC150
   inputs`), time-invested (`8 months extending…`), training origin
   (`trained on Stockfish`), tamper evidence (`tamper-evident, checksum`),
   local-only boundary claims, and verifiable access claims (`free`, `open
   source`, `no sign up`) — its top trigger at 22.5% is still under the
   tripwire. domain_expert gains counted-scale evals, measured unit
   economics (`$24.57 per million`), hardware specs (`3k sprite pixels per
   line`), re-runnable behavior (`deterministic verdict programs`),
   trust-surface removal (`no sign up`) and a small negative for
   AI-as-category-adhesive titles.

Recalibrated numbers: coverage 24/40 (60%, was 10/40=25%) · kills still 0/40
(untested-not-proven stands) · no trigger over the 50% tripwire.
Per persona (posts with evidence): skeptic 1→12 · domain_expert 2→10 ·
maker 4→7 · security_reader 4→7 · tired_dev 4→5 · front_page_regular 8 (unchanged).

Honest readings after recalibration:

- The remaining 16 silent posts are mostly pure product names with no claim
  to check ([0] Roffume, [15] Scrolling Text Generator). Silence now means
  "no claim to weigh", which is what it should mean — though for several,
  a maker-side note ("demo at …", "no account needed") is the fix, and the
  missing_advice paths say so.
- The title-doc change makes quotes cite `show_hn_title.md` when the match
  is in the title — check those comments read naturally before this feeds
  the forecaster.
- skeptic's 22.5% access-claims trigger is the new watch item: it must not
  creep past 50% on a larger sample.

## Results (baseline)

- **Coverage: 10/40 posts (25%) trigger any persona.** 30 of 40 real posts are
  invisible to the whole persona set.
- **Kill phrases: 0/40.** Nothing in the real sample reads as disqualifying to
  any persona.
- **No generic triggers** over the 50% tripwire — the top trigger fires on
  17.5% of posts (`front_page_regular: I (built|made|wrote|hacked)`).
- Per persona (posts with evidence / total evidence hits):
  front_page_regular 8/16 · maker 4/6 · security_reader 4/9 · tired_dev 4/5 ·
  domain_expert 2/8 · skeptic 1/1.
- Structural driver: only 12/40 posts have selftext at all. 28 surfaces are
  title-only, and real Show-HN titles carry little trigger vocabulary
  ("Show HN: Roffume – Add fragrance to your resume with roff").

## Honest reading

1. **Our drafts overestimated trigger density.** Hand-written surfaces flatter
   the triggers; the real world is thinner. This is exactly the failure the
   held-out set exists for — and it is now measured, not assumed.
2. **Low coverage is partly structural, not purely a trigger bug.** A
   title-only post is a thin surface by design (the forecaster flags low
   signal rather than inventing reaction). But a compass that under-reacts to
   75% of real posts is a compass whose silence carries little information —
   silence should mean "no strong signal," not "no patterns matched."
3. **skeptic (1/40) and domain_expert (2/40) are near-deaf on real posts.**
   Their triggers expect citation/benchmark vocabulary that Show-HN culture
   mostly doesn't put in titles. Either their patterns need recalibration to
   the genre, or their stances genuinely are rare on Show-HN — the A/B can't
   distinguish those; a human reading the fired quotes should.
4. **Kill phrases never firing is untested, not proven.** Zero kills on 40
   posts means the kill path has no real-world calibration data yet. One
   over-eager kill phrase is worse than ten weak evidence triggers.

## Next

- Kill-phrase calibration needs a sample with known-bad posts (e.g. Show HN
  posts flagged/removed) — don't tune kills against a clean sample.
- Watch skeptic's access-claims trigger (22.5%) on the next pinned sample.
- The held-out personas stay locked until Casey's authored triggers land.
