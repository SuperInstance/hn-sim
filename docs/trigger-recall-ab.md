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

- Recalibration pass on skeptic/domain_expert patterns against the fired-quote
  list (`--json` output), with the pins re-based deliberately.
- Kill-phrase calibration needs a sample with known-bad posts (e.g. Show HN
  posts flagged/removed) — don't tune kills against a clean sample.
- The held-out personas stay locked until Casey's authored triggers land.
