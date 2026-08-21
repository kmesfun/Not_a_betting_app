# PRD: Live Season Simulator — NBA & NFL

Status: Draft v2 (revised post-critique)
Owner: Kenny
Last updated: August 19, 2026

> **Changelog from v1:** Elevated data-licensing risk to a blocking assumption (§1a); clarified Monte Carlo methodology to season-level rather than per-game (§6); added tail-probability noise mitigation note (§6); resolved the betting-market-as-ground-truth tension explicitly (§6); flagged NFL public player-value data as a feasibility risk (§6); made award-slate scope consistent across leagues (§5, P0.4); added a latency NFR for the callable interface (P0.6); added off-day handling to ingestion acceptance criteria (P0.1); added a shorter-horizon calibration proxy metric (§7); noted auth/identity as a P1 dependency (§5); updated timeline to gate Phase 1 on the licensing assumption (§9).

## 1. Problem Statement

Sports fans and fantasy/betting-adjacent users want a daily, data-driven read on "who's most likely to win it all right now" — but that answer changes constantly as trades, injuries, and game results happen. Existing tools (ESPN FPI, Vegas odds, etc.) give point-in-time win probabilities but don't let a user get a personal, on-demand, explainable simulation that updates itself daily and can be "called" like a service rather than browsed on a website. There's no single tool that combines Monte Carlo season simulation, roster-event-aware adjustments (trades/injuries), and per-position weekly player rankings in one queryable app.

### 1a. Blocking assumption — must validate before Phase 1 starts

This product depends on ingesting real-time schedules, box scores, transactions, and injury reports (P0.1). Commercial sports-data providers (e.g., Sportradar, Genius Sports, Stats Perform) frequently license "probability" or "odds-like" derivative products only to parties operating as, or contracting with, licensed gambling operators — independent of whether the product itself takes bets. Being a non-betting product (§3) does not automatically exempt this app from that restriction; it is a data-contract question, not a product-scope question.

**Before any Phase 1 engineering work begins, confirm with at least one candidate data provider that a public-facing championship/award/ranking-probability product is permitted under their standard commercial license.** If it isn't, the fallback options (delayed/free-tier data, a narrower internal-only tool, or restructuring as licensed-partner-only) need to be decided before architecture is finalized, since they have different latency and hosting implications. This is now the single critical-path item in §9, ahead of simulation engine work.

## 2. Goals

1. Produce a daily-refreshed championship probability distribution for all 30 NBA teams and 32 NFL teams, driven by Monte Carlo season simulation.
2. Automatically ingest trades and injuries and re-weight team strength within 24 hours of the event, measurably changing downstream title odds in a direction and magnitude consistent with the event.
3. Generate a weekly MVP-style probability ranking (league MVP equivalent) plus win-likelihood rankings for other major awards (e.g., NFL: OPOY/DPOY/OROY/Coach of the Year; NBA: DPOY/6MOY/MIP/ROY/Coach of the Year).
4. Produce weekly positional player power rankings (e.g., NFL: QB1–QB32, RB1–RB40, etc.; NBA: PG/SG/SF/PF/C top-N).
5. Expose all of the above through a callable app/API interface so a user can request "today's update" on demand rather than visiting a dashboard.

## 3. Non-Goals

* Betting/odds product: This is a probability and ranking tool, not a sportsbook — no bet placement, no line-shopping, no real-money integration. (Legal/compliance overhead not justified for v1. See §1a — this framing does not by itself resolve data-licensing risk.)
* Play-by-play or live in-game win probability: We simulate at the game/season level, not live inside a game clock. (Different data pipeline and latency requirements — future consideration.)
* Full player-vs-player fantasy scoring / fantasy team optimization: We rank real players by performance/impact, not fantasy points against a user's roster. (Separate product surface.)
* Leagues beyond NBA/NFL (MLB, NHL, soccer, etc.) in v1. (Scope control — architecture should stay league-agnostic to make this easy later.)
* Building a proprietary predictive player-performance model from scratch in v1: v1 leans on established public rating inputs (e.g., team Elo/SRS-style ratings, injury-adjusted depth charts) rather than a custom ML model trained in-house. (Faster time to market; a custom model is a P2 investment. **Feasibility caveat:** NBA has reasonably rich public advanced-stats/win-share data; NFL's public equivalent is materially thinner. NFL trade/injury re-weighting in Phase 3 may need a simpler proxy value metric — e.g., snap-share-weighted approximate value — rather than a true win-shares figure. Validate data availability per league before committing to the same model shape for both.)

## 4. User Stories

* As a sports fan, I want to ask the app "who's most likely to win the NBA championship right now" so that I get an always-current answer without hunting across sites.
* As a fan, I want the app to automatically account for a trade or injury that happened this week so that the odds I see reflect reality, not stale preseason numbers.
* As a fan, I want a weekly MVP probability leaderboard so that I can track the MVP race like a live standings board.
* As a fan, I want award-race odds (DPOY, ROY, Coach of the Year, etc.) updated weekly, not just MVP.
* As a fan, I want positional player rankings updated weekly (e.g., "who's the current QB1") so that I can settle debates with data instead of opinion.
* As a fan, I want to "call" the app daily (via chat, notification, or API) and get a fresh update, rather than remembering to check a website.
* As a fan, I want to see why the odds moved (e.g., "Team X's title odds dropped 4% after Star Player Y's ACL injury") so that the numbers feel trustworthy, not a black box.
* As a returning user, I want to subscribe to a specific team/player so my daily update is personalized instead of a generic league-wide dump.

## 5. Requirements

### Must-Have (P0)

**P0.1 — Daily data ingestion pipeline**

* Ingest daily schedule, box scores/final results, transactions (trades, signings, waivers), and injury reports for NBA and NFL.
* Acceptance criteria:
  * Given a completed game yesterday, when the daily job runs, then that result is reflected in team ratings before the next simulation run.
  * Given a trade is reported by the data provider, when the next daily cycle runs, then both teams' rosters/ratings reflect the trade.
  * Given a player is newly listed as "out" or "IR", when the next cycle runs, then that team's simulated strength adjusts down for that player's estimated on-court/on-field value.
  * **Given no games were played and no roster events occurred (off-day, All-Star break, bye week, off-season), when the daily job runs, then it completes successfully as a no-op and the "as of" timestamp on the last valid simulation still advances so users can distinguish "checked today, nothing changed" from a stale/broken pipeline.**

**P0.2 — Monte Carlo season simulator**

* Run N independent full-season simulations (default N = 1,000). Within each simulation, every remaining regular-season game is simulated exactly once using current team strength ratings, home/away, rest, and injury-adjusted rosters; results roll forward through standings and playoff bracket logic to a single champion per simulation. Championship/conference/playoff-appearance probabilities are the fraction of the N simulations in which that outcome occurred for a given team — this is a season-level Monte Carlo, not N independent draws per individual game.
* Acceptance criteria:
  * Given current standings and remaining schedule, when a full simulation batch runs, then every team has a championship probability, conference/division-winner probability, and playoff-appearance probability that sum consistently (championship ≤ conference title ≤ playoff appearance).
  * Simulation batch completes within a defined SLA (see Open Questions) so a "daily" cadence is actually achievable.
  * Results include a standard error given the sample size (binomial SE ≈ sqrt(p·(1−p)/N)), not just a point estimate.
  * **For teams whose probability estimate is small enough that the standard error is a large fraction of the estimate (rule of thumb: SE > 20% of p), the daily update must either increase N for that team via targeted re-sampling or visually flag the estimate as low-confidence — day-over-day sampling noise must not be presented as a real odds movement (see P1.4).**

**P0.3 — Trade/injury re-weighting logic**

* A defined, documented model for translating a roster event into a rating adjustment (e.g., value-over-replacement style delta applied to team strength inputs), phased in over a configurable ramp rather than applied instantly.
* Acceptance criteria:
  * Given two teams complete a trade, when ratings recompute, then the receiving team's championship odds move in a direction consistent with the traded player's value delta.
  * Given a star player is ruled out for the season, when ratings recompute, then that team's title odds drop by a magnitude roughly consistent with the player's estimated win-share contribution.
  * **Validation methodology note:** the above is calibrated against a holdout of historical trades/injuries where pre/post betting-market odds are known, since that is the best available ground truth for "the market's" reaction. This uses market odds strictly as an offline calibration signal during model development — it is not surfaced to users and does not change the product's non-betting scope (§3).

**P0.4 — MVP and award probability model**

* Weekly-updated probability rankings for: League MVP (NBA/NFL). Beyond MVP, **v1 covers a fixed, identical-shape minimum slate per league — one offense-side and one defense-side award (NBA: DPOY, ROY; NFL: OPOY, DPOY) — with the full award slate (6MOY/MIP/Coach of the Year for NBA; OROY/DROY/Coach of the Year for NFL) as a P1 expansion once the minimum slate is validated.** This resolves the prior inconsistency where Coach of the Year was required for one league and optional for the other.
* Acceptance criteria:
  * Given current season stats and team performance, when the weekly award job runs, then each award produces a ranked list of candidates with a win probability that sums to ~100% across a defined, capped field of live candidates (e.g., top 15 by a pre-filter heuristic) — the cap must be explicit so "sums to 100%" is well-defined.
  * Rankings are explainable — each candidate shows the top 2-3 statistical/team-success factors driving their rank.

**P0.5 — Weekly positional player power rankings**

* For each league, rank the top players at each position (NFL: QB/RB/WR/TE/etc.; NBA: PG/SG/SF/PF/C) on a weekly cadence, using recent performance + season-long value.
* Acceptance criteria:
  * Given a completed week of games, when the ranking job runs, then a full ordered list per position is generated and timestamped.
  * Rankings visibly change week over week in response to performance, injury, or role changes (not static).

**P0.6 — Callable app/API interface for daily updates**

* Users can request an on-demand "today's update" (championship odds, MVP odds, positional rankings, notable changes) through a defined callable interface (chat command, push notification, or REST/API endpoint — see Open Questions for exact surface).
* Acceptance criteria:
  * Given a user requests an update, when the request is made, then the response reflects the most recent completed daily/weekly simulation run (not a stale cached version from before the last data refresh).
  * Response clearly states the "as of" timestamp of the underlying simulation so users know its freshness.
  * Users can scope a request to a specific league, team, or player rather than only getting the full league dump.
  * **Non-functional: since the simulation batch runs on a schedule (not per-request), an on-demand request must be served from precomputed results in well under 1 second — the callable interface reads the latest batch output, it does not trigger a new simulation synchronously.**

### Nice-to-Have (P1)

* P1.1 Push notifications/proactive alerts when a team's title odds move beyond a threshold (e.g., ±5%) due to a trade or injury, rather than requiring the user to ask. (Movement threshold must be evaluated against the noise floor established in P0.2's low-confidence flag, so real alerts aren't swamped by sampling-noise alerts.)
* P1.2 Historical odds tracking — a simple trend line of a team's or player's odds over the season so users can see trajectory, not just today's snapshot.
* P1.3 Personalized subscriptions (favorite teams/players) that tailor the daily update content and shorten it. **Depends on user identity/auth existing, which is not built in P0 — this is a hard prerequisite, not just a nice-to-have feature toggle.**
* P1.4 "Explain this movement" natural-language summaries auto-generated after each daily run (e.g., a 2-3 sentence recap of the day's biggest odds movers and why).
* P1.5 Support for mid-season coaching changes as a re-weighting trigger, not just player trades/injuries.
* P1.6 Full award slate expansion per league (see P0.4).

### Future Considerations (P2)

* P2.1 Expansion to additional leagues (MLB, NHL, NCAA) using the same simulation engine.
* P2.2 In-house trained predictive rating model (replacing/augmenting third-party ratings) once enough historical validation data is collected.
* P2.3 Live in-game win-probability simulation (not just pre-game/season level).
* P2.4 Social/competitive layer — users compare their "who I think will win" picks against the model.
* P2.5 Voice-assistant integration for the "call it and get an update" experience.

## 6. Simulation & Ranking Methodology (Reference)

This section documents the intended approach at a level engineering can build against; exact formulas should be finalized during technical design.

* **Team strength rating:** Start from an Elo- or SRS-style continuously-updated power rating per team, recalculated after every completed game.
* **Roster adjustment layer:** Maintain a per-player "value" figure (e.g., a win-shares/WAR-style estimate — see §3 feasibility caveat on NFL data availability). When a trade or injury occurs, adjust the team rating by the net value delta of players in/out, phased in over a short ramp (new teammates take a few games to integrate; this should be configurable, not instant).
* **Game simulation:** For each remaining game, simulate score/outcome via the team ratings + home-court/field adjustment + rest/travel factors.
* **Season roll-forward (Monte Carlo):** Run N independent full-season simulations (default N = 1,000): in each one, chain individual game sims through the remaining schedule and playoff seeding/bracket rules once, producing one full outcome per simulation. Aggregate across the N simulations to get per-team distributions of: playoff appearance, conference title, championship, each with a standard error. **This is the resolved definition of "1,000 simulations" — it is 1,000 full seasons, not 1,000 independent replays of each individual game.** For teams with low win probabilities, apply the noise-floor handling described in P0.2 rather than displaying raw day-to-day sampling variance as signal.
* **Award models:** Separate lightweight models per award, primarily statistical-production-driven (MVP/OPOY/etc. correlate heavily with team win% + individual counting/efficiency stats); recompute weekly rather than nightly since award races move slower than title odds. Candidate field is capped (see P0.4) so win-probability normalization is well-defined.
* **Positional rankings:** Blend season-long efficiency/production metrics with a recency weighting (e.g., last 3-4 games weighted more heavily) so rankings react to hot/cold streaks and injuries without being purely reactive to one game.

## 7. Success Metrics

### Leading indicators

* Daily active "calls" to the app (target: define after soft launch baseline; track week-over-week growth). **Only meaningful once the free/paid/personal-tool question in §8 is resolved — if v1 stays single-user, replace with a simpler "did today's call succeed and complete within SLA" health check.**
* % of users who scope requests to a specific team/player vs. full league dump (signals personalization demand → prioritize P1.3).
* Time from a real-world trade/injury event to it being reflected in the app's odds (target: < 24 hours, stretch < 6 hours).

### Lagging indicators

* Calibration accuracy: at season end, do the teams given ~X% championship odds actually win about X% of the time across a multi-season sample (Brier score / calibration curve). **This has a multi-season feedback loop and won't produce a usable signal until well after v1 ships. Add a shorter-horizon proxy: weekly calibration of the playoff-appearance probability, which resolves within a single season and can catch a systematically miscalibrated model months earlier than the championship-level Brier score would.**
* Retention: % of users still calling the app weekly by week 8 of a season.
* Explainability satisfaction: qualitative/survey signal on whether users trust the "why odds moved" explanations.

## 8. Open Questions

* [Stakeholder] What is the actual delivery surface for "wrapped in an app so users can call it" — a chat-based assistant integration, a push-notification mobile app, a REST API for other apps to consume, or all three? This materially changes scope and should be resolved before technical design.
* [Data/Eng — **blocking, see §1a**] What data provider(s) will supply real-time schedules, box scores, transactions, and injury reports, and does their license permit a public-facing probability/ranking product? Cost, rate limits, and licensing terms here drive feasibility of the entire product, not just refresh cadence.
* [Eng] What's the compute budget/SLA for running 1,000 full-season simulations across 62 teams across two leagues, daily? This determines whether "daily" is realistic league-wide or needs to be scoped (e.g., full daily, but position rankings weekly as already planned).
* [Product] Should award races (MVP, DPOY, etc.) only cover the P0.4 minimum slate, or expand to the full award slate each league gives out? (P0.4 now defaults to minimum-slate-for-v1, full slate deferred to P1.6, pending confirmation.)
* [Legal] Any concerns using team/player names, logos, or third-party stats commercially, depending on data licensing terms? (Related to §1a but distinct — this is trademark/publicity-rights exposure, not data-contract exposure.)
* [Product] Free vs. paid tiers — is this a personal tool, or intended for broader/public distribution (affects auth, rate limiting, monetization, and which leading indicators in §7 are meaningful)?

## 9. Timeline Considerations

* **Critical path, gating everything else: resolve the data-licensing assumption in §1a.** No Phase 1 engineering estimate below is reliable until this is confirmed, since a negative answer changes the architecture (e.g., delayed/free-tier data source, or a non-public internal tool) rather than just the schedule.
* Suggested phasing (assumes §1a resolves favorably):
  * **Phase 0 (new):** Confirm data provider licensing permits this product; select provider; stand up mock-data-driven engine in parallel so simulation/architecture work isn't blocked on the legal answer.
  * **Phase 1:** Single league (recommend starting with whichever is in-season at build time) — core simulator + championship odds + callable interface, no awards/positional rankings yet. Can begin against mock data before Phase 0 fully resolves, but cannot go live against real data until it does.
  * **Phase 2:** Add MVP/award probability model (P0.4 minimum slate) + weekly positional rankings for that same league.
  * **Phase 3:** Add second league; harden trade/injury re-weighting using Phase 1-2 validation data; revisit the NFL player-value data feasibility caveat from §3.
  * **Phase 4 (P1 items):** Notifications, personalization (requires auth — see P1.3), historical trend tracking, full award slate (P1.6).
* Seasonality note: NFL and NBA seasons don't fully overlap — build the ingestion/simulation core to be league-config-driven so both can share infrastructure rather than being two separate codebases.
