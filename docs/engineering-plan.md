# Phase 1 Engineering Plan

**Goal:** a live product with real users by **October 26, 2026**, one week before the YC Winter 2027 deadline of November 2.

**Scope:** one league, championship odds, market divergence detection, push digest, risk-tiered parlays. No awards, no positional rankings, no second league.

Working code for the core is already in `title-engine/` — simulation engine, devigging, divergence detection, parlay builder, and API routes, with 80 passing tests. This plan covers what's left.

---

## The schedule

Five weeks, one engineer, assuming evenings and weekends rather than full-time. If it's full-time, everything compresses and you should pull Week 5 items forward rather than adding scope.

| Week | Ships | Success looks like |
|---|---|---|
| **1** (Sep 21-27) | Real data flowing | Daily job pulls live schedule/results/injuries, produces real odds |
| **2** (Sep 28-Oct 4) | Real markets connected | Model-vs-market deltas computed from live Polymarket/Kalshi prices |
| **3** (Oct 5-11) | Public surface | One-page site live, digest sending to you |
| **4** (Oct 12-18) | Beta users | 20-40 people receiving the digest |
| **5** (Oct 19-25) | Evidence | Track record page live, application written |
| **Oct 26** | **Submit** | | |

The critical path is Weeks 1-2. Everything after depends on the pipeline being real.

---

## Week 1 — Real data

**Pick the league first.** NFL is the better choice for this window: it's in season now, has the highest news intensity per week (more divergence events to catch), and its free data via nflverse is the best-maintained open sports dataset available. NBA's season is also underway and has more games, which makes it the better long-term daily habit — but NFL gives you more shots at a documented divergence in five weeks, and that documented divergence is the single most valuable thing you can have on Oct 26.

**Tasks:**

1. **Wire `ingest/nfl.py` to live data.** `snapshot_from_frame` is written and takes a dataframe; `load_snapshot` calls nflreadpy. Verify field names against the real feed — that's the main unknown.
2. **Build the ratings bootstrap.** Currently `RatingBook.initial` generates random ratings. Replace with: initialize at 1500, replay the season's completed games through `apply_result`, and you have real Elo. This is ~20 lines and it's what makes the odds real rather than illustrative.
3. **Wire injuries to `RosterEvent`.** nflverse exposes injury reports. The mapping from "player X is out" to a `win_share_delta` is the hard judgment call — see below.
4. **Daily job.** A single cron entry running ingest → rate → simulate → store. Persist to SQLite for now; Postgres when there's a reason.

**The one genuinely hard modeling problem:** translating a player's absence into a team rating delta. `ELO_PER_WIN_SHARE = 28.0` in `ratings.py` is a placeholder and it is the most important constant in the system.

Two options, in order of preference:
- **Fit it.** Take historical star injuries where you know the pre/post market move, and solve for the constant that reproduces those moves. This is a few hours of work and gives you a defensible number.
- **Start with published value metrics.** For NFL, approximate positional value (QB dominates everything else by a wide margin — a starting QB is worth several times any other position). Crude but directionally right.

Do not skip this and leave the placeholder. An injury model that moves odds by the wrong magnitude produces divergence alerts that are wrong, and one confidently wrong alert costs more trust than ten correct ones earn.

**Week 1 done when:** the daily job runs unattended and produces championship odds you'd defend.

---

## Week 2 — Markets

1. **Map outcomes to venue markets.** The unglamorous, necessary piece: a table mapping your team ids to Polymarket market ids and Kalshi tickers. Do it by hand — there are 32 teams and it'll take an hour, versus a day for fuzzy matching that you'd need to verify by hand anyway.
2. **Verify the clients against live endpoints.** They're written against documented shapes and unit-tested with realistic fixtures, but never run against production. Budget an hour for field-name reality.
3. **Devigging sanity check.** After devigging, model and market should disagree in *both* directions across the board. If every team looks "undervalued," the devig isn't working — that's a bias, not a signal. `test_devigs_before_comparing` encodes this, but check it against real prices too.
4. **Start logging.** Every day, append model probability, each venue's price, and the delta to a table. **This is the most valuable thing you build in Week 2** — it's the calibration record, and it only accumulates in real time. You cannot backfill it. Start it before anything else is polished.

**Week 2 done when:** you can answer "where do we disagree with the market right now?" from real data.

---

## Week 3 — Public surface

Keep this deliberately small. It's a credibility surface, not a product surface.

1. **One page.** Current odds, the model-vs-market table, today's parlays, and an email signup. Server-rendered from the API. No framework needed — this is a table and a form.
2. **Digest sending.** Wire `build_digest` to an email service. Send to yourself only for a week. Watch what it does on quiet days — if it's sending something every day, tune `AlertRule`; silence on a quiet day is correct behavior.
3. **Disclaimers and 18+ gate.** Per the compliance notes. Do this now, not later — it's ten minutes now and an awkward retrofit later.

**Week 3 done when:** you've received a week of digests and they're worth reading.

---

## Week 4 — Beta users

**This is the week that determines whether the application is strong.** Everything before it is prerequisite.

1. **Recruit 20-40 people.** Where they actually are: prediction-market communities on Reddit and Discord, Kalshi/Polymarket sports traders, sports analytics forums. Post the track record, not the product — "here's a model that's been disagreeing with Kalshi, here's what happened" is a better hook than "check out my app."
2. **Instrument open rates.** You need to be able to say "N people, X% still opening in week three." Basic email analytics is enough.
3. **Talk to ten of them.** Not a survey — actual conversations. What made them open it? What would make them pay? Record the quotes; specific quotes beat paraphrase in an application.
4. **Watch for your divergence.** When a real injury or trade hits, screenshot everything: your model's timestamp, the market's price before and after, when it moved. **That artifact is worth more than every other thing in this plan.**

**Week 4 done when:** you have a retention number and, with luck, a documented divergence.

---

## Week 5 — Evidence and application

1. **Track record page.** Publish the complete log: every divergence called, resolved and unresolved, wins and losses. Complete, not curated — both because a curated record destroys the credibility that is the whole asset, and because performance claims in this category carry FTC substantiation exposure.
2. **Calibration numbers.** Brier score against resolved outcomes, model vs market. Even a small sample is worth showing if you show the sample size honestly.
3. **Write the application** using the draft. Every number traceable to something real.
4. **Record the video** showing the live product, ideally walking through a real divergence.

---

## Architecture

Deliberately boring. Nothing here needs to scale yet, and complexity now costs you weeks you don't have.

```
cron (daily)
  │
  ├─ ingest        nflverse → SeasonSnapshot
  ├─ rate          replay results → Elo; apply RosterEvents
  ├─ simulate      50,000 sims → championship/conference/playoff odds
  ├─ markets       Polymarket + Kalshi → devig → normalized probabilities
  ├─ diverge       model vs market → Divergence list → append to log
  ├─ parlays       build tiered combinations from this run's legs
  └─ digest        build_digest → send if non-empty
         │
         ▼
      SQLite  ──→  FastAPI  ──→  one page + email
```

**Deployment:** a single small instance. The simulation takes 0.3 seconds; this runs comfortably on the cheapest tier anywhere. Don't build for scale you don't have.

**Storage:** SQLite until it hurts. The tables you need:

| Table | Holds | Why |
|---|---|---|
| `runs` | timestamp, league, n_sims, git sha | Reproducibility — you'll want to know which model version made a call |
| `odds` | run_id, team, probability, se | The model's history |
| `market_quotes` | timestamp, venue, outcome, raw price, devigged | Market history |
| `divergences` | run_id, outcome, model, market, delta, z, alerted | **The calibration record** |
| `outcomes` | what actually happened | Needed to score anything |
| `subscribers` | email, scope, threshold | |

The `divergences` + `outcomes` pair is the asset. Everything else is replaceable.

---

## What to explicitly not build in Phase 1

Each of these is a week you don't have:

- **Awards and positional rankings.** Phase 2. They're retention features, not the differentiator.
- **The second league.** Phase 3. Prove the loop on one.
- **A native mobile app.** Deferred indefinitely per PRD 9.1 — it's the slowest surface to iterate and the only one that invites gambling-adjacent app review.
- **Accounts and auth.** Email address in a table is enough for 40 beta users.
- **Player props.** Requires per-player outcome distributions the architecture doesn't build. PRD 9.8.
- **Explicit correlation modelling.** Exclusion is already implemented and cannot be wrong. Model it when you have data to fit against.
- **A paid data provider.** Free sources cover the MVP. Spend money when there's revenue.

---

## Risks, honestly

| Risk | Reality | What to do |
|---|---|---|
| **No divergence happens in five weeks** | Real. Injuries to stars are not on a schedule | Backtest against last season's injuries instead. Weaker than a live call, much better than nothing. Start this in Week 3 as insurance rather than waiting to see |
| **Injury→rating mapping is wrong** | The likeliest source of bad alerts | Fit it against historical moves in Week 1. Don't ship the placeholder |
| **Free data breaks** | Moderate; nflverse is well-maintained but has no SLA | Cache every fetch. A stale run beats a missing one |
| **Market APIs differ from docs** | Likely in small ways | Budget the hour in Week 2. Parsing is already tested against fixtures |
| **Nobody signs up** | The real risk | This is a Week 4 signal you need early. If 40 people won't take a free digest, the thesis is wrong, and knowing that in October is far better than in January |

That last row is the one to take seriously. The engineering here is genuinely tractable — a sub-second simulation and a data pipeline are well inside what you've built before. The open question is whether people want it, and the entire plan is structured to answer that by Oct 26 rather than to produce a more polished product.

---

## First session

If you want a concrete start:

```bash
cd title-engine
pip install -e ".[dev,nfl]"
pytest                    # confirm the 80 tests pass
python demo.py            # see the whole pipeline on synthetic data
```

Then open `src/title_engine/ingest/nfl.py` and make `load_snapshot` work against the real feed. That's the first real task, and everything downstream of it is already written and tested.
