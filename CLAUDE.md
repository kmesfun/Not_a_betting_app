# CLAUDE.md — context for Not_a_betting_app

Read this before changing anything. It carries decisions that were made
deliberately and aren't obvious from the code. Several of them look like things
worth "simplifying" and are not.

---

## What this is

An independent pricing layer for prediction markets, starting with NBA
championship odds.

We simulate the remaining season, compare our probabilities against live prices
on Polymarket and Kalshi, and alert when they disagree past a threshold. The
disagreements are caused by news: a star gets hurt at 7pm, our model reprices
immediately, the market often takes hours to a day to catch up.

**The simulator is the engine. Divergence detection is the product.**

That distinction drives everything. "Here are today's championship odds" is a
reference tool people check occasionally — it does not earn a daily open,
because odds barely move on a quiet day. "The market hasn't priced last night's
injury yet" does. If a change makes the odds prettier but weakens the divergence
signal, it's the wrong change.

The repo name is a joke about the compliance posture. Worth knowing that if this
ever goes public, a name that protests its own innocence reads worse than a
neutral one, given the product's whole legal position is that it is analysis
rather than wagering.

---

## Layout

```
simulator/src/simulator/
  simulate.py      Monte Carlo engine (pure Python, string-keyed teams)
  ratings.py       Elo + RosterEvent (value_delta in ELO POINTS, ramp in GAMES)
  bracket.py       Seeding and series
  events.py        Before/after explainability for a roster event
  mock_data.py     Deterministic mock ratings + schedule
  report.py        "Today's update" payload
  cli.py / api.py  Callable interfaces
  static/          Dashboard
  markets/         ← NEW: Polymarket + Kalshi clients, devigging
  divergence.py    ← NEW: model vs market, alert rules, digest state
  parlay.py        ← NEW: risk-tiered parlays with correlation exclusion
  ingest/news.py   ← NEW: TypeSafe news → RosterEvent
```

Everything marked NEW is additive — no existing file was modified.

## Commands

```bash
cd simulator
pip install -r requirements.txt && pip install -e .
pytest                                  # 143 tests
python -m simulator.cli update           # callable interface
uvicorn simulator.api:app --reload       # API + dashboard at /
```

---

## The constraints that are not negotiable

### 1. Market prices must be devigged before comparison

Raw prices across mutually exclusive outcomes sum to more than 1 — the excess is
the overround. Our probabilities sum to exactly 1.

Comparing them directly makes the market look more confident than it is on
*every single outcome*, so the model appears systematically right and we'd ship
a bias while calling it a signal. `markets/normalize.py` handles this;
`test_devigs_before_comparing` asserts post-devig deltas go both directions.

Default is the POWER method for championship markets — it shrinks longshots more
than proportional devigging and better matches favourite-longshot bias.

### 2. Correlated parlay legs are never multiplied

Legs from the same game or team are not independent. Multiplying their
probabilities is a bug, not a simplification.

Every `Leg` carries `correlation_keys` and the builder refuses to combine legs
sharing one. Exclusion is deliberately conservative — it cannot produce a wrong
number, whereas modelling correlation badly can. Move to explicit modelling only
when there's data to fit against.

### 3. No model-derived number enters the probability pipeline

`ingest/news.py` uses TypeSafe's System One model to read injury and transaction
reporting. **The model classifies; code assigns numbers.**

The model returns *labels* ("franchise player", "out for the season"). Code looks
the pair up in `ELO_DELTA_TABLE` to get the magnitude. No float that came out of
a model ever becomes a `value_delta`.

Why this matters enough to test structurally:

- Odds stop being reproducible — replaying last month's inputs against a newer
  model version yields different history.
- Backtesting becomes dishonest. You cannot replay last season against a model
  that didn't exist then and call that a track record.
- The divergence claim collapses into "the market disagrees with a language
  model's guess."

`tests/test_news.py::TestModelCodeBoundary` enforces this, including a
structural test that fails if anyone adds a magnitude field to `Classification`.

Confidence gates *whether* we act, never *what* the number is: auto-apply above
0.90, hold for review 0.50–0.90, discard below 0.50, plus a separate
confirmation check so hedged reporting ("could miss time") never moves anything.

`KeywordClassifier` runs offline with no API key. It's deliberately assigned
mid-range confidence so its output always lands in review, and it doubles as a
control — if it does nearly as well as the model on your sample, the model isn't
paying for itself.

### 4. Sim count is a precision decision, not a cost decision

`run_monte_carlo` defaults to `n_sims=1000`. Benchmarking says that's too few for
anything in the tail:

| True probability | ±SE at n=1,000 | at n=50,000 |
|---|---|---|
| 40% | ±1.55% (4% rel.) | ±0.22% |
| 5% | ±0.69% (14% rel.) | ±0.10% |
| **1%** | **±0.31% (31% rel.)** | ±0.04% (4%) |

At 1,000 sims a genuine longshot carries ±31% relative error. It's worse for
parlays, where leg errors compound: a five-leg long shot is ±18% — "1 in 19,290"
might really be 1 in 16,322.

The existing `low_confidence` flag is the right instinct and partially covers
this. The fuller fix is more simulations.

**The catch:** the current engine is pure Python, so it's O(n_sims × games) and
50,000 sims would take tens of seconds. A numpy-vectorized version (schedule as
incidence matrices, so accumulating wins is one matmul) runs 50,000 sims for two
leagues in **0.32s on 2 cores** — about 1,000× faster. `docs/benchmarks/` has
the benchmark and the precision analysis.

This is an open decision, not a done deal: vectorizing means adding numpy and
reworking `simulate.py` from string-keyed dicts to integer-indexed arrays. Worth
it, but it's a real change to working code and should be deliberate.

---

## Legal constraints that shape the code

Not decoration — these reflect a real exposure analysis.

- **Never present tiers as profit advice.** "Safe" means higher modeled
  probability, never "likely to profit."
- **Publish the complete track record, including losses.** Performance claims
  here carry FTC substantiation exposure, and a curated record destroys the
  credibility that is the whole asset.
- **No bet placement, no stake/payout calculator, no link into a wagering
  flow.** The product is analysis; keeping it that way is what keeps it out of
  gambling regulation.
- **No affiliate revenue in v1.** It triggers registration requirements in
  several states and compromises the independence being sold.

Consumer analysis content is broadly legal — Nevada's "information service"
licensing (NRS 463.01642) applies to selling to a *licensed sports pool*, not to
consumer content. Web-first also avoids app-store gambling review entirely.

---

## Docs

- `docs/PRD.md` — the original PRD this repo was built from.
- `docs/PRD-v4.md` — supersedes it. Same product, but with every open question
  researched and answered (Section 9): data providers, market API access,
  compute budget, award scope, legal exposure, monetization, the daily-open
  problem. **Read v4's Section 9 before planning work.** The two are kept side
  by side rather than merged so the original stays intact; fold them together
  when convenient.
- `docs/engineering-plan.md` — five-week build to a fundable state.
- `docs/yc-application.md` — draft answers. YC Winter 2027 closes **Nov 2**;
  target submitting Oct 26 with real usage data rather than a spec.
- `docs/benchmarks/` — the simulation benchmark and precision analysis behind
  the sim-count argument above.

---

## The two things most likely to bite

**`ELO_DELTA_TABLE` in `ingest/news.py` is a placeholder**, calibrated by
judgment rather than data. The sanity anchor is roughly 10 Elo ≈ one win over 82
games, so a franchise player lost for the season lands near -110. That's about
the right magnitude, and "about right" is not good enough to publish odds on.
Fit it against historical injuries where the pre/post market move is known.
Until then every downstream number inherits the guess's error, and a confidently
wrong alert costs more trust than ten correct ones earn.

**Distribution is the real risk, not the engineering.** A sub-second simulation
and a data pipeline are tractable. Whether anyone opens a daily digest is not
known yet, and the build plan is structured to answer that in weeks rather than
to produce a more polished product.

---

## Not yet verified against anything live

The Polymarket, Kalshi, and TypeSafe clients are written against documented API
shapes and unit-tested with realistic fixtures, but were built in a container
that couldn't reach any of those hosts. Budget an hour of field-name reality on
first contact with each. Same for real data ingestion — the simulator still runs
on `mock_data.py`.

---

## Working style

Push back when something is wrong rather than implementing it as asked. Several
decisions here came from exactly that: the original "1,000 simulations" figure
was in the spec and was wrong, and the correction came from benchmarking rather
than agreeing.

Say plainly when something hasn't been verified. "Written against the docs but
never run against the live API" is useful; quiet confidence is not.
