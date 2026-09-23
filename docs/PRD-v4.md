# PRD: Live Season Simulator — NBA & NFL

**Status:** Draft v4 — open questions answered (see Section 9)
**Owner:** Kenny
**Last updated:** September 20, 2026

---

## 0. Startup Framing (YC-style)

YC evaluates ideas on a short list of things: a sharp problem statement, a wedge (not a platform), evidence of demand, a founder who can build it fast, and a path to a large market. This section front-loads that framing before the PRD detail, since it's what a partner or angel reads first.

**One-liner:** A daily-refreshing Monte Carlo simulator for NBA/NFL championship and award odds — adjusted in real time for trades and injuries, and benchmarked against prediction markets (Polymarket, Kalshi) — delivered as a callable app instead of a dashboard you have to remember to check.

**Why now:**
- Prediction markets (Polymarket, Kalshi) went mainstream in the US in 2025-2026 and legitimized "probability of an outcome" as a consumer-facing product category, not just a Vegas-adjacent niche. Sports odds are now one of the highest-volume categories on both platforms.
- Sports betting handle and engagement have grown every year since PASPA fell; a large, monetizable, habitual audience already exists and is comfortable with probabilistic framing ("62% to win it all") rather than raw money lines.
- LLM-based agents make an always-on, queryable, explainable analytics product buildable by a small team fast — the "ask it and get an answer" UX YC likes (a wedge, not a research project) is now cheap to build well.
- No incumbent combines season-long Monte Carlo simulation + roster-event-aware re-rating + prediction-market benchmarking + a callable/agentic interface in one product today. ESPN FPI/BPI, Vegas odds boards, and Polymarket/Kalshi each do one piece.

**The wedge (start narrow):** Don't try to out-build ESPN or out-market a sportsbook on day one. The wedge is: **we tell you when the market is wrong.** The model detects that a trade or injury has changed a team's real title odds *before Polymarket and Kalshi have repriced it*, and pushes that divergence to you the same day.

The simulator is the engine; **divergence detection is the product.** This distinction matters more than it sounds — see 9.9. "Here are today's championship odds" is a reference tool people check occasionally; "the market hasn't priced this injury yet" is a reason to open something daily. No one else produces the second thing: ESPN publishes odds with no market comparison, Polymarket and Kalshi publish prices with no independent model, and Twitter has the news but no pricing. The intersection is the entire opportunity.

**Why a founder-market fit story matters here:** be ready to answer "why you" — infra/backend engineering background (high-QPS APIs, pipeline reliability) is directly relevant to running a nightly simulation pipeline at scale reliably; that's worth stating explicitly in a deck, since YC weights founder-market fit heavily for a data-pipeline-heavy product like this.

**Risks a YC partner will probe (be ready, don't hide these):**
- *Distribution risk:* sports content is a crowded, retention-hard category. What's the specific reason someone opens this daily instead of ESPN or Twitter? **This remains the single biggest risk.** 9.9 gives the answer the product should be built around (divergence alerts, pushed), but it's an answer that has to be *proven with retention data*, not asserted in a deck.
- *Data cost risk:* sports data licensing (real-time injuries/transactions, especially NFL) can be expensive and gate margins at scale.
- *Legal/compliance risk:* comparing against or referencing prediction markets, and potentially embedding market prices, brushes up against gambling-adjacent regulation in some states even without taking bets. The parlay feature raises this further — "parlay" is explicit betting terminology, and even as pure informational content, some states restrict "tout" services (selling or promoting sports picks) or require disclaimers/licensing. Needs a legal read before go-to-market, not after — this is the single highest-priority open item given how central parlays now are to the product.
- *"Nice tool" vs. "venture-scale business" risk:* the honest test is whether this becomes a habitual, monetizable daily product (subscription, affiliate/referral to prediction markets, B2B API licensing) or stays a fun personal project. Pick the monetization thesis before writing the pitch (see Section 9).

**Suggested proof points before raising:** a working single-league (start with whichever is in-season) MVP, real daily active usage data (even from a small beta cohort), and at least one concrete instance of the model calling a trade/injury-driven odds swing that later tracked with how Polymarket/Kalshi and Vegas moved. That's the "traction + why it's real" story YC wants over a deck of projections.

---

## 1. Problem Statement

Sports fans and prediction-market users want a daily, data-driven read on "who's most likely to win it all right now" — but that answer changes constantly as trades, injuries, and game results happen. Existing tools (ESPN FPI, Vegas odds, Polymarket, Kalshi) each give a point-in-time number, but none of them (a) run a transparent, explainable Monte Carlo simulation the user can query on demand, (b) automatically re-weight for roster news within a day, and (c) show how the model's view compares to what real money is pricing on Polymarket/Kalshi. There's no single tool that combines simulation, roster-event awareness, market benchmarking, and per-position weekly rankings in one queryable app.

## 2. Goals

1. Produce a daily-refreshed championship probability distribution for all 30 NBA teams and 32 NFL teams, driven by **50,000** Monte Carlo simulations per remaining game. *(Raised from 1,000 — see 9.4: the benchmark shows 1,000 is a precision liability, not a compute saving, and 50,000 costs 0.3 seconds.)*
2. Automatically ingest trades and injuries and re-weight team strength within 24 hours of the event, measurably changing downstream title odds.
3. Generate a weekly MVP-style probability ranking (league MVP equivalent) plus win-likelihood rankings for other major awards.
4. Produce weekly positional player power rankings.
5. Expose all of the above through a callable app/API interface so a user can request "today's update" on demand.
6. **Benchmark every model-generated probability against the live equivalent market on Polymarket and Kalshi**, so users (and investors) can see where the model agrees, disagrees, and — over time — whether it's better calibrated than the market.
7. **Surface model-derived parlay combinations spanning a risk spectrum** — from high-probability "safe" combinations to low-probability "long shot" combinations — so users get a curated, explainable set of multi-leg picks rather than having to build their own from raw odds.
8. Validate a viable path to a funded, standalone company: a wedge feature with daily habitual usage, a defensible data/model asset, and a monetization thesis — not just a working simulator.

## 3. Non-Goals

- **Betting/odds product**: No bet placement, no line-shopping, no real-money integration in v1. This includes the parlay feature (Section 5, P0.8): it surfaces model-derived combinations as **informational content/analysis** — probabilities and explanations, not a slip a user submits or funds through the app. (Legal/compliance overhead not justified pre-seed; revisit once there's traction and legal counsel.)
- **Live in-game win probability**: We simulate at the game/season level, not live inside a game clock. (Future consideration.)
- **Full fantasy team optimization**: We rank real players by performance/impact, not fantasy points against a user's roster. (Separate product surface.)
- **Leagues beyond NBA/NFL in v1** — keep the wedge narrow; architecture should stay league-agnostic so this is cheap to add later.
- **A proprietary trained ML model in v1**: lean on established public rating inputs (Elo/SRS-style, injury-adjusted depth charts) rather than an in-house model trained from scratch. (Faster to ship a defensible wedge; a custom model is a later moat-building investment, not a v1 requirement.)
- **Executing trades on Polymarket/Kalshi, or any market-making/arbitrage functionality.** The market comparison is informational (model vs. market), not a trading product. (Keeps this out of derivatives/broker-dealer regulatory territory for v1.)

## 4. User Stories

- As a sports fan, I want to ask the app "who's most likely to win the NBA championship right now" so that I get an always-current answer without hunting across sites.
- As a fan, I want the app to automatically account for a trade or injury that happened this week so that the odds reflect reality, not stale numbers.
- As a fan, I want to see how the model's title odds compare to what Polymarket and Kalshi are currently pricing, so that I can tell whether the model thinks a team is under- or over-valued by the market.
- As a fan, I want a weekly MVP probability leaderboard so that I can track the MVP race like a live standings board.
- As a fan, I want award-race odds (DPOY, ROY, Coach of the Year, etc.) updated weekly.
- As a fan, I want positional player rankings updated weekly.
- As a fan, I want to "call" the app daily (via chat, notification, or API) and get a fresh update.
- As a fan, I want to see *why* the odds moved and whether the market agrees, so the numbers feel trustworthy, not a black box.
- As a returning user, I want to subscribe to a specific team/player so my daily update is personalized.
- As an early investor/advisor, I want a simple way to see the model's historical calibration versus the market's, so I can judge whether this is a defensible data product or just a fun simulator.
- As a fan, I want a "safe" parlay of the model's highest-confidence picks for the day/week, so I can see the combinations the model itself is most sure about.
- As a fan, I want a "long shot" parlay built from lower-probability but plausible outcomes, so I can see what a high-upside combination looks like without building it myself from scratch.
- As a fan, I want each parlay leg explained (why the model likes this outcome) and the combined probability shown plainly, so I understand the real odds rather than just a curated list with no reasoning.
- As a fan, I want to see how a parlay's combined probability compares to what it would cost/pay on Polymarket or Kalshi, consistent with the model-vs-market comparison elsewhere in the app.

## 5. Requirements

### Must-Have (P0)

**P0.1 — Daily data ingestion pipeline**
- Ingest daily schedule, box scores/final results, transactions, and injury reports for NBA and NFL.
- *Acceptance criteria:*
  - [ ] Given a completed game yesterday, when the daily job runs, then that result is reflected in team ratings before the next simulation run.
  - [ ] Given a trade is reported, when the next daily cycle runs, then both teams' rosters/ratings reflect the trade.
  - [ ] Given a player is newly listed as "out"/"IR", when the next cycle runs, then that team's simulated strength adjusts down accordingly.

**P0.2 — Monte Carlo season simulator (50,000 sims/remaining game)**
- Simulate every remaining game 50,000 times using current team strength ratings, home/away, rest, and injury-adjusted rosters, rolled forward through playoff bracket logic to a champion.
- Implementation note: vectorize across simulations (represent the schedule as incidence matrices so win accumulation is a matmul rather than a per-sim loop). The benchmarked prototype in 9.4 runs 50,000 sims for both leagues in 0.32s on 2 cores using this approach; a naive per-sim Python loop will be ~1,000× slower and will make the SLA look like a real constraint when it isn't.
- *Acceptance criteria:*
  - [ ] Every team has a championship probability, conference/division-winner probability, and playoff-appearance probability that sum consistently.
  - [ ] A full both-league refresh completes in under 60 seconds (benchmark suggests this is achievable by two orders of magnitude; the loose SLA leaves room for a richer per-game model later).
  - [ ] Results include a standard error alongside every published probability, not just a point estimate — and the UI never displays more precision than the sample size supports.

**P0.3 — Trade/injury re-weighting logic**
- A defined, documented model for translating a roster event into a rating adjustment.
- *Acceptance criteria:*
  - [ ] Given two teams complete a trade, the receiving team's odds move in a direction consistent with the traded player's value delta (validated against historical trades with known pre/post market odds).
  - [ ] Given a star player is ruled out for the season, that team's title odds drop by a magnitude roughly consistent with their estimated win-share contribution.

**P0.4 — Market benchmarking layer (Polymarket + Kalshi)**
- Pull live/latest odds for the equivalent markets on Polymarket and Kalshi (e.g., "NBA Champion 2026-27", "Super Bowl LXI Winner") for every team/outcome the simulator also prices.
- Normalize market prices (implied probability from contract price, net of fees where disclosed) onto the same scale as the model's simulated probabilities so they're directly comparable.
- Surface a simple model-vs-market delta per team/outcome (e.g., "Model: 18% · Polymarket: 12% · Kalshi: 13% → model sees this team as undervalued by ~5-6pts").
- Log this comparison daily so a historical "was the model or the market more accurate" record accumulates over the season — this is the calibration evidence referenced in Section 0 and Section 8.
- *Acceptance criteria:*
  - [ ] Given a live market exists on Polymarket or Kalshi for a given outcome, when the daily update runs, then the app shows model probability, each available market's implied probability, and the delta, with an "as of" timestamp for the market price.
  - [ ] Given a market doesn't yet exist for a given outcome (e.g., a minor award), the app clearly shows "no market" rather than a blank or misleading zero.
  - [ ] A rolling calibration log (model vs. resolved outcomes vs. market vs. resolved outcomes) is stored so this can be reported on later, even if not surfaced in the UI in v1.

**P0.5 — MVP and award probability model**
- Weekly-updated probability rankings for League MVP (NBA/NFL) and at least 2 additional major awards per league.
- *Acceptance criteria:*
  - [ ] Each award produces a ranked list of candidates with a win probability summing to ~100% across live candidates.
  - [ ] Rankings are explainable — each candidate shows the top 2-3 factors driving their rank.

**P0.6 — Weekly positional player power rankings**
- Rank top players at each position weekly, using recent performance + season-long value.
- *Acceptance criteria:*
  - [ ] A full ordered list per position is generated and timestamped weekly.
  - [ ] Rankings visibly change week over week in response to performance, injury, or role changes.

**P0.7 — Callable app/API interface for daily updates**
- Users can request an on-demand "today's update" through a defined callable interface.
- *Acceptance criteria:*
  - [ ] Response reflects the most recent completed daily/weekly run, not a stale cache.
  - [ ] Response states the "as of" timestamp.
  - [ ] Users can scope a request to a specific league, team, or player.

**P0.8 — Risk-tiered parlay builder**
- Generate a daily/weekly slate of model-derived multi-leg combinations ("parlays") spanning a defined risk spectrum, built entirely from the simulator's own outputs (game winners/spreads-equivalent, title/award leaders, positional-ranking-implied props if available) rather than sourced from a third party.
- **Risk tiers** (combined probability = product of leg probabilities, with a correlation check — see below):
  - *Safe:* combined probability roughly ≥ 60%. Fewer legs (2-3), each individually high-confidence.
  - *Balanced:* combined probability roughly 25-60%. 3-4 legs, mixing high-confidence and moderate picks.
  - *High-risk / long shot:* combined probability roughly < 25%. 4+ legs or lower-probability individual legs, explicitly framed as low-probability/high-upside.
  - Exact thresholds are tunable — pick brackets that produce a genuinely useful spread (e.g., 3 tiers minimum) rather than three tiers that all cluster together.
- **Correlation handling (do this correctly, not naively):** legs from the same game or involving the same team/player are statistically correlated (e.g., "Team A wins" and "Team A's star player wins MVP-of-the-week" move together). Naively multiplying independent-leg probabilities overstates or understates the true combined probability for correlated legs. The builder must either (a) exclude correlated leg combinations, (b) flag them explicitly as correlated with an adjusted estimate, or (c) model the correlation directly — pick one and document it; silently multiplying correlated probabilities as if independent is a correctness bug, not a simplification.
- Each leg shows its individual model probability and a one-line "why" (same explainability bar as P0.3-P0.5); each parlay shows the combined probability and, where a comparable multi-leg market exists on Polymarket/Kalshi, the market-implied price for comparison (reusing the P0.4 normalization logic).
- Clear, persistent framing as analysis/entertainment content, not a bet slip: no "place this parlay" action, no stake/payout calculator implying real-money wagering, and (pending the legal review in Section 9) a visible responsible-gambling-style disclaimer if the tier language ("safe," "long shot") could otherwise read as betting advice.
- *Acceptance criteria:*
  - [ ] Given a daily/weekly run completes, when parlays are generated, then at least one parlay exists in each defined risk tier, each with 2+ legs drawn only from that run's own simulated probabilities.
  - [ ] Given a parlay contains legs that are statistically correlated, when it's displayed, then the correlation is either avoided, flagged, or accounted for in the combined-probability calculation — never silently multiplied as if independent.
  - [ ] Given a comparable market exists on Polymarket/Kalshi, the parlay's combined probability is shown alongside the market-implied equivalent.
  - [ ] No leg or parlay includes a call-to-action to place a bet, stake money, or link to a betting execution flow.

**P0.9 — Divergence alerts & daily push digest** *(promoted from P1.1 — see 9.9)*
- Proactively notify users when (a) a team's title odds move beyond a threshold (e.g. ±5%) due to a trade/injury, or (b) the model-vs-market delta crosses a threshold — "the market hasn't caught up to this injury yet."
- Delivered as a push digest (email/SMS in v1), not only as an on-demand response. This is the daily retention mechanism; the callable interface (P0.7) is the supplement to it, not the other way round.
- *Acceptance criteria:*
  - [ ] Given a roster event moves a team's odds past the threshold, when the next cycle runs, then subscribed users receive a digest naming the team, the size of the move, the cause, and the current market comparison.
  - [ ] Given a day with no divergence above threshold, then **no digest is sent** — silence is the correct behavior, and a digest that fires daily regardless trains users to ignore it.
  - [ ] Users can set their own threshold and scope (all teams vs. followed teams).

### Nice-to-Have (P1)

- **P1.2** Historical odds tracking — trend line of a team's/player's odds over the season, plotted alongside the market's line for the same outcome.
- **P1.3** Personalized subscriptions (favorite teams/players).
- **P1.4** "Explain this movement" natural-language daily recap, including notable model-vs-market divergences.
- **P1.5** Support for mid-season coaching changes as a re-weighting trigger.
- **P1.6** Public, shareable "model calibration" page/leaderboard (model accuracy vs. Polymarket vs. Kalshi vs. Vegas over the season) — this doubles as a marketing/credibility asset for fundraising and user acquisition.
- **P1.7** Parlay track record — log each generated parlay (by tier) and its actual hit rate over time, so "Safe tier hits ~X% of the time, Long-shot tier hits ~Y%" becomes a verifiable, published stat rather than a claim. Strong credibility asset, same spirit as P1.6.
- **P1.8** User-customizable parlays — let a user pick their own legs from the model's individual picks and see the combined (correlation-adjusted) probability, rather than only browsing the three pre-built tiers.

### Future Considerations (P2)

- **P2.1** Expansion to additional leagues (MLB, NHL, NCAA) using the same engine.
- **P2.2** In-house trained predictive rating model, once enough historical validation data is collected.
- **P2.3** Live in-game win-probability simulation.
- **P2.4** Social/competitive layer — users compare their picks against the model (and against the market).
- **P2.5** Voice-assistant integration.
- **P2.6** B2B API licensing of the odds/calibration feed to media outlets, fantasy platforms, or prediction-market-adjacent tools — a plausible second revenue line once the core data asset is proven (see Section 9).

## 6. Simulation & Ranking Methodology (Reference)

- **Team strength rating:** Elo- or SRS-style continuously-updated power rating per team, recalculated after every completed game.
- **Roster adjustment layer:** Per-player "value" figure (win-shares/WAR-style). Trades/injuries adjust team rating by the net value delta, phased in over a short ramp rather than instantly.
- **Game simulation:** Each remaining game simulated via team ratings + home-court/field adjustment + rest/travel factors, repeated 1,000 times for a distribution, not a point estimate.
- **Season roll-forward:** Chain game sims through the remaining schedule + playoff seeding/bracket rules to produce per-team distributions of playoff appearance, conference title, championship.
- **Market normalization:** Convert Polymarket/Kalshi contract prices to implied probabilities (adjusting for fee structure where applicable) on the same outcome definitions the simulator uses, so "model probability" and "market probability" are apples-to-apples.
- **Award models:** Statistical-production-driven, correlated with team win% + individual stats; recomputed weekly since award races move slower than title odds.
- **Positional rankings:** Blend season-long efficiency/production with recency weighting (last 3-4 games weighted more) so rankings react to streaks/injuries without being purely reactive to one game.
- **Parlay combination selection:** From the pool of legs eligible on a given day/week (game winners, title/award leader probabilities, etc.), generate candidate combinations, compute combined probability accounting for correlation (see P0.8), bucket into risk tiers by combined probability, and select the clearest/most explainable combination per tier rather than an exhaustive list.

## 7. Success Metrics

**Leading indicators**
- Daily active "calls" to the app (define baseline after soft launch; track week-over-week growth — this is the core retention metric YC will ask about).
- % of users who scope requests to a specific team/player vs. full league dump (signals personalization demand).
- Time from a real-world trade/injury event to it being reflected in the app's odds (target < 24h, stretch < 6h).
- % of daily updates where a user views the model-vs-market comparison (validates that feature as the differentiator, not just a nice-to-have).
- % of users who view/engage with parlay tiers, and which tier (Safe/Balanced/Long-shot) gets the most engagement — signals which risk appetite to design future features around.

**Lagging indicators**
- Calibration accuracy: at season end, do teams given ~X% championship odds actually win about X% of the time (Brier score / calibration curve) — reported both in isolation and relative to Polymarket/Kalshi/Vegas.
- Parlay tier accuracy: actual hit rate per tier vs. the tier's stated combined probability (validates P0.8/P1.7 aren't just a gimmick — this is a second, independently checkable calibration story for fundraising).
- Retention: % of users still calling the app weekly by week 8.
- Conversion (once monetized): free → paid conversion rate, or click-through rate on any market referral/affiliate links.
- Explainability/trust: qualitative signal on whether users trust the "why odds moved" and "vs. market" explanations.

## 8. Startup Validation Plan (pre-fundraise checklist)

This is the sequence to actually get funded, not just build the product:

1. **Ship the wedge, not the vision.** Build P0.1-P0.4, P0.7, P0.8 (parlay tiers), and P0.9 (divergence alerts) for a single, in-season league first. P0.9 is the retention loop and P0.8 is the shareable hook; together they're the reason anyone comes back. Award rankings and positional rankings (P0.5/P0.6) can follow — good retention features, not the differentiator.
2. **Get 2-4 weeks of real daily-use data**, even from a small beta group (10-50 people is fine). YC cares far more about "here's proof people come back daily" than a polished but unused product.
3. **Capture at least one real trade/injury calibration story** — a case where the model moved odds before or in line with the market, ideally documented with timestamps and screenshots. This is the single best pitch-deck slide for this idea.
4. **Get a legal read on the Polymarket/Kalshi comparison and any gambling-adjacent framing** before broad launch — confirm displaying market prices (without facilitating trades) is clean in your target states, and confirm terms-of-service compliance for pulling Polymarket/Kalshi data.
5. **Decide the monetization thesis explicitly** (see below) before writing a deck — "we'll figure out monetization later" is a weak answer to a YC partner for a consumer sports product.
6. **Write the one-liner and wedge into the application/pitch verbatim from Section 0** — keep it to the single differentiated claim (simulation + roster-event-aware re-rating + market benchmarking, delivered as a callable daily product) rather than listing every feature.

**Monetization options to evaluate (pick one primary, don't try all at once):**
- Consumer subscription (premium leagues/teams, notifications, historical trend data — P1.1-P1.3 gated behind a paywall).
- Affiliate/referral relationships with Polymarket/Kalshi (or sportsbooks, if later in scope) — monetizes the comparison feature directly, but adds regulatory surface area; needs legal review first.
- B2B API/data licensing (P2.6) — media, fantasy platforms, or research desks license the odds + calibration feed. Slower to close deals but a cleaner, more defensible SaaS-shaped revenue line for a technical founder.

## 9. Resolved Decisions

Each item below was an open question in v3. Research and a benchmark prototype resolved most of them; what genuinely remains open is in Section 10.

### 9.1 Delivery surface → **Web + API first. No native mobile app in v1.**

Build the simulation service API-first (REST/JSON), then expose it through a simple web app plus an LLM-callable tool interface (function-calling schema / MCP server). Defer native mobile.

**Reasoning:**
- Native mobile is the slowest surface to iterate on and the only one that drags the product into Apple/Google gambling-adjacent app review (see 9.6). Avoiding that for v1 removes an entire class of launch risk for zero loss of core value.
- An API-first core means the chat interface, web app, digest emails, and any future mobile app are all thin clients over one service — no rework later.

**Important correction to the product framing:** "callable" is a *pull* interaction, and pull-based products lose to push-based ones for daily-habit formation. A user will not remember to call this every day. **The daily retention loop should be a push digest (email/SMS to start), with the callable interface as the on-demand supplement.** This reframes P0.7 and promotes P1.1 (notifications) into the must-have set — see 9.9, which argues this is the actual product.

### 9.2 Sports data provider → **Free/open sources for MVP, paid tier once there's traction.**

| Stage | Source | Cost | Covers |
|---|---|---|---|
| MVP / beta | **nflverse** (`nflreadpy`, `nfl_data_py`) for NFL | Free | Schedules, results, play-by-play, **injuries**, depth charts |
| MVP / beta | **nba_api** (stats.nba.com wrapper) for NBA | Free | Schedules, box scores, rosters |
| Production | **API-Sports** or **SportsDataIO** | ~$50–500/mo | Reliable injuries + transactions with an SLA |
| Avoid pre-revenue | **Sportradar**, **OpticOdds** | Enterprise annual contracts | Not worth it before revenue |

**Two honest caveats:**
1. **Free sources have no SLA and ambiguous commercial-use terms.** They are fine for prototyping and a beta cohort; they are not a foundation for a funded company. Budget for the paid tier at roughly the point you have paying users or a raise.
2. **Transactions/trades are the weakest feed in every cheap provider.** Injury reports are well covered; structured trade data is not. Expect to supplement with news parsing — or enter them manually during beta. A trade happens a few times a week, not a few times an hour, and hand-entering them lets you ship sooner without building a parser first.

### 9.3 Polymarket & Kalshi API access → **Both are readable, free, and well within the rate budget.**

- **Polymarket Gamma API** (`gamma-api.polymarket.com`): fully public, **no authentication**, ~4,000 requests / 10s. CLOB read endpoints ~9,000 / 10s. Note the quirk that outcome prices return as a JSON-encoded *string*, not an array — parse before indexing. Geo-restrictions apply to *order placement*, not reads, which is irrelevant here since the product never trades (Section 3).
- **Kalshi API** (`docs.kalshi.com`): public market data is readable without full trading authentication. Rate limits are tiered; the entry **Basic tier is 200 read tokens/sec** (most requests cost 10 tokens, so ~20 req/sec). A daily-refresh product needs a few hundred requests per day. This is not a constraint.

**Conclusion:** rate limits and cost are non-issues. The one thing still to verify is redistribution terms in Kalshi's Developer Agreement — narrow enough that it stays in Section 10 rather than blocking design.

### 9.4 Compute budget & SLA → **A non-issue. And the 1,000-sim requirement should be raised to 50,000.**

I built a vectorized prototype (Elo ratings, full remaining schedule, conference seeding, best-of-7 playoff brackets for NBA, single-elimination for NFL) and benchmarked it on **2 CPU cores**:

| Sims per league | NBA | NFL | **Full refresh, both leagues** |
|---|---|---|---|
| 1,000 | 0.007s | 0.002s | **0.005s** |
| 10,000 | 0.044s | 0.013s | **0.047s** |
| 50,000 | 0.233s | 0.090s | **0.324s** |
| 200,000 | 0.981s | 0.385s | **1.30s** |

A full daily refresh of both leagues at 50,000 sims takes **under a third of a second**, or about **0.16 minutes of CPU per month**. The simulation is not a cost center; it will run inside a cron job on the smallest instance any host offers.

**This changes a stated requirement.** The PRD specified 1,000 simulations. The benchmark shows 1,000 is not a compute constraint — it's a *precision liability*, and the extra precision is free:

| True probability | ±SE at n=1,000 | at n=10,000 | at n=50,000 |
|---|---|---|---|
| 40% | ±1.55% (4% rel.) | ±0.49% | ±0.22% |
| 15% | ±1.13% (8% rel.) | ±0.36% | ±0.16% |
| 5% | ±0.69% (14% rel.) | ±0.22% | ±0.10% |
| **1%** | **±0.31% (31% rel.)** | ±0.10% (10%) | ±0.04% (4%) |

At 1,000 sims a genuine longshot's odds carry **±31% relative error** — the difference between a 0.7% and a 1.3% title chance, both reported as "1%."

**It matters far more for parlays (P0.8), where leg errors compound:**

| Parlay | n=1,000 | n=50,000 |
|---|---|---|
| Safe (3 legs @ 75/70/68%) | 35.7%, ±3.5% rel. | ±0.5% rel. |
| Balanced (4 legs @ 58/55/50/48%) | 7.66%, ±6.0% rel. | ±0.9% rel. |
| Long shot (4 legs @ 25/20/15/10%) | "1 in 1,333" — really 1 in **1,162–1,563** | 1 in 1,306–1,362 |
| Long shot (5 legs @ 20/18/15/12/8%) | "1 in 19,290" — really 1 in **16,322–23,577** | 1 in 18,807–19,799 |

Publishing "1 in 19,290" when the true value could be 1 in 16,322 is a number the product cannot defend — and the long-shot tier is exactly where users will scrutinize the math hardest.

> **Recommendation: change the requirement from 1,000 to 50,000 simulations.** It costs 0.3 seconds. Keep 1,000 only as a fast path for interactive "what-if" queries where the user is exploring, not reading published odds.

*Caveat on the benchmark:* the prototype uses team-level Elo with a synthetic schedule and simplified seeding (no play-in, no NFL reseeding/tiebreakers). A production model with richer per-game simulation could be 10–100× slower. Even at 100×, a 50,000-sim refresh is ~32 seconds — still trivially inside a daily SLA. The conclusion holds with a wide margin.

### 9.5 Award coverage → **Major awards only, selected by a simple rule: does a prediction market exist for it?**

Cover MVP, DPOY, ROY, and Coach of the Year per league, plus OPOY/OROY/DROY for NFL. Skip the minor slate.

**Reasoning:** the product's differentiator is model-vs-market comparison. An award with no Polymarket/Kalshi market has nothing to compare against, so it delivers a bare model number with no cross-check — the weakest version of the product. Voter-driven awards are also genuinely hard to model, and a confident miss on an obscure award costs more credibility than the award adds value. Letting market existence be the filter is self-maintaining: as markets get listed for more awards, the eligible set grows on its own.

### 9.6 Legal exposure → **Lower than v3 assumed, but with one real risk that isn't the one the PRD was worried about.**

**Sports "tout"/handicapping content is broadly legal in the US.** Publishing or selling sports analysis and picks is protected opinion/content, and a large industry already operates openly (Action Network, VSiN, Covers, and many others). The frequently-cited Nevada licensing regime is narrower than it appears: NRS 463.01642 defines an "information service" as one that "sells and provides information **to a licensed sports pool**" — that is, B2B sales into a sportsbook, not consumer-facing content. It also carves out general-circulation media. **A consumer analysis app is not captured by it.**

**App store policies only bite if you ship native mobile.** Apple's and Google's gambling rules (licensing per jurisdiction, geo-restriction, AO/adult rating, free-download requirement) attach to *real-money gambling* apps. A picks/analysis app with no wagering generally ships under standard rules — but it does invite reviewer scrutiny and inconsistent outcomes. **This is a second independent argument for the web-first decision in 9.1.**

**The actual risk is FTC deceptive-advertising exposure on performance claims.** This is where tout services have historically gotten into real trouble, and it lands directly on the features most central to the pitch (P1.6 calibration page, P1.7 parlay track record). Performance claims must be substantiated and not cherry-picked.

> **Mitigations to build in from day one, not retrofit:**
> - Publish the **complete** track record including losing stretches — never a selected window. The calibration story is the whole asset; a curated version destroys its credibility and creates liability at the same time.
> - Frame tiers as probabilities, not advice. "Safe" must visibly mean "higher modeled probability," never "likely to profit."
> - No profit, ROI, or earnings claims anywhere — not in marketing, not in the app.
> - 18+ gate and a plain "analysis/entertainment, not betting advice" disclaimer.
> - Keep the no-affiliate-revenue stance for v1 (see 9.7).

### 9.7 Monetization and its regulatory cost → **Subscription first. Don't take affiliate revenue at launch.**

Of the three options in Section 8, affiliate/referral is the one that changes the legal posture: gambling-affiliate marketing triggers registration or licensing obligations in several states and converts the product from "analysis content" into "paid acquisition for a gambling operator." That's a materially different regulatory category, and taking it on pre-traction buys risk before there's a business to protect.

**Recommended order: (1) consumer subscription, (2) B2B API/data licensing, (3) affiliate — only with counsel, and only once the track record is an asset worth monetizing.**

### 9.8 Parlay legs → **Team-level outcomes only in v1.**

Legs come from game winners, title/conference odds, and award-leader probabilities. **No player props in v1.**

**Reasoning:** props require per-player outcome distributions, and the v1 architecture deliberately doesn't build those — it models team Elo plus a value-over-replacement adjustment (Section 6), which produces team-level probabilities and a player *value* estimate, not a player's stat distribution. Props would need a whole additional modeling layer. They're also where correlation is worst (a QB's passing yards and his team winning are strongly linked), which is the exact failure mode P0.8 already has to guard against. Add props in Phase 2, on top of the positional-rankings model, which provides the player-level substrate.

### 9.9 The daily-open question → **The current feature set doesn't justify a daily open. This needs a reframe, and it's the most important finding here.**

The honest read: **championship odds don't move enough day-to-day to earn a daily check.** On a day with no trade, no injury, and a normal slate, the model's title odds move a fraction of a point. "Here are the odds" is a reference tool — something users visit when they happen to wonder, which is a weekly-or-less behavior. Shipping that and hoping for daily retention is the most likely way this fails, and a YC partner will find it in one question.

**The reframe: this isn't an odds dashboard, it's a divergence detector.**

The daily hook is not *"here are today's odds"* but *"here's what changed, and where the market hasn't caught up yet."* Concretely, the push digest leads with:

> *Denver: model −4.2% after the Murray injury. Kalshi still pricing them at the pre-injury level. Largest model-vs-market gap on the board right now.*

That earns a daily open, because it's time-sensitive and actionable — and **nobody else produces it.** ESPN publishes odds without market comparison. Polymarket and Kalshi publish prices without an independent model. Twitter has the news but no pricing. The intersection is the whole product.

**What this changes:**
- The wedge in Section 0 should be restated as *"we tell you when the market is wrong"*, not *"we simulate seasons."* The simulator is the engine; divergence detection is the product.
- **P1.1 (threshold alerts) moves from Nice-to-Have to P0.** It's the retention mechanism, not a nice-to-have.
- Model-vs-market delta (P0.4) becomes the primary surface in every view, not a comparison column.
- Days with no meaningful divergence should send *nothing*. A digest that fires daily regardless trains users to ignore it; one that fires when something actually moved trains them to read it.

### 9.10 Solo vs. co-founder → **Look for a distribution co-founder, not a second engineer.**

YC funds solo founders, so this isn't disqualifying — but it does weight teams, and the specific gap here is clear. The technical half of this product is, per 9.4, a cron job running a sub-second simulation plus a data pipeline: well-covered by a backend/infra background, and not the hard part. **The hard part is distribution in a saturated sports-content market**, which 9.9 identifies as the top risk.

A second backend engineer adds capacity where there's already slack. A co-founder who brings a sports audience, consumer-growth experience, or media distribution addresses the thing most likely to kill this. If a co-founder search is on the table at all, weight it that way.

## 10. Remaining Open Questions

Narrower than before, and none of these block starting Phase 1:

- **[Legal]** Kalshi's Developer Agreement and Polymarket's ToS — confirm redistribution/display of prices in a commercial third-party product is permitted, and note any attribution requirement. (Reads are technically open; this is a terms question, not an access question.)
- **[Legal]** One counsel review before public launch covering: FTC substantiation posture on the track-record features, disclaimer wording, and the 18+ gate. Budget a single consultation, not an ongoing engagement.
- **[Product]** Exact risk-tier thresholds for P0.8 — the 60% / 25% brackets are a starting point and should be tuned once real leg distributions exist, so the three tiers come out genuinely distinct rather than clustered.
- **[Product]** Which league to launch with, which depends on build timing relative to the seasons. NFL has higher per-game stakes and news intensity (better divergence signal per week); NBA has more games (more simulation surface, more frequent updates). NFL is likely the better *demo*, NBA the better *daily habit*.
- **[Eng]** Correlation modeling approach for P0.8 — exclude, flag, or model. Recommend starting with *exclude* (no two legs from the same game or team), which is trivial to implement and can't be wrong, then moving to explicit modeling once there's data.

## 11. Timeline Considerations

- **Dependency:** ~~Data provider selection must be finalized before the simulation engine starts~~ — **no longer a blocker.** Per 9.2, free sources (nflverse, nba_api) cover the MVP, and per 9.3 both prediction-market APIs are open. Phase 1 can start immediately; the paid-provider decision moves to the point of real traction.
- **Suggested phasing:**
  - *Phase 1 (the fundable wedge):* Single league, in-season — simulator + championship odds + Polymarket/Kalshi benchmarking + **divergence alerts (P0.9)** + risk-tiered parlays + callable interface. No awards/positional rankings yet. Target: something demoable and in daily use within weeks, not months.
  - *Phase 2:* Add MVP/award probability model + weekly positional rankings for that same league.
  - *Phase 3:* Add second league; harden trade/injury re-weighting using Phase 1-2 validation data; publish the calibration track record (P1.6).
  - *Phase 4:* Notifications, personalization, historical trend tracking; begin monetization test.
- **Seasonality note:** NFL and NBA seasons don't fully overlap — build the ingestion/simulation core league-config-driven so both share infrastructure.
