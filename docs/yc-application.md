# YC Application Draft — Winter 2027 (W27)

**Deadline: Sunday, November 2, 2026, 8:00pm PT.** Decisions by December 11. Batch runs January–March 2027 in San Francisco.

**That is six weeks from today (Sept 20).** This matters more than anything else in this document, so read the timing section first.

---

## Read this before the answers: the timing decision

You have two options and they are not close in strength.

**Option A — apply now, with a PRD.** Your answer to "How far along are you?" is *"I've specced it."* Every YC partner reads hundreds of those. A spec is not evidence that anyone wants the thing.

**Option B — ship Phase 1 over the next four weeks, apply ~Oct 26 with real usage data.** Your answer becomes *"Live since early October. N people get the divergence digest. The model flagged the [X] injury 14 hours before Kalshi repriced it."* That is a different application entirely.

Six weeks is enough for Option B, and the engineering plan is built around hitting it. The simulator already works. **Apply in the last week of October, not now.** YC also lets you update your application with progress after submitting, so shipping continues to help right up to the decision.

One caution on the "apply 3-4 weeks early" advice that circulates: it's real, but it optimizes for interview scheduling. Applying with traction beats applying early without it. Target Oct 26 — that's a week of buffer before the deadline and four weeks of build time.

---

## Company

### Describe what your company does in 50 characters or less.

> **We find mispriced sports prediction markets.** *(44 characters — verified)*

Alternates, all verified under 50:
- `We tell you when betting markets are wrong.` (43)
- `Sports odds model that beats prediction markets.` (48)
- `Mispricing alerts for sports prediction markets.` (48)

Pick based on the video: whichever sentence you can say out loud without flinching.

### What is your company going to make?

> We run an independent simulation of the NBA and NFL seasons and compare it, continuously, against the live prices on Polymarket and Kalshi. When the two disagree past a threshold, we tell you.
>
> The disagreements are caused by news. A star tears an ACL at 7pm; our model repriced that team's title odds by the time the box score posted; the prediction market often takes hours to a day to fully absorb it. That gap is the product. Users get a push alert: *"Denver −4.2% after the Murray injury. Kalshi still at the pre-injury price. Largest gap on the board."*
>
> Underneath it is a Monte Carlo engine that simulates every remaining game 50,000 times, rolls the results through playoff brackets, and re-rates teams within hours of any trade or injury. On top of it we publish championship odds, award races, positional player rankings, and risk-tiered parlay combinations built from our own probabilities — but the simulation is the engine, not the product. The product is knowing when the market is wrong before the market does.

### Where do you live now, and where would the company be based after YC?

Oakland, CA → San Francisco. *(You're already in the Bay. Say so — it's a small positive.)*

---

## Founders

### Why did you pick this idea to work on? Do you have domain expertise in this area?

**Be honest about which expertise you have.** You do not have sports-betting domain expertise, and claiming it is the fastest way to get caught in the interview. What you have is the expertise this problem actually requires:

> The hard part of this is not the sports. It's running a data pipeline that ingests injury reports, transactions, and results every day without breaking, re-rating 62 teams, and getting a correct number out the other end on a schedule — reliably enough that people trust an alert that tells them a market is wrong.
>
> I spent six years on exactly that class of problem: high-QPS backend services and platform reliability at YouTube (InnerTube core services), Microsoft, and Yahoo's anti-abuse platforms. Pipelines that had to be right, on time, at scale, with no one watching.
>
> I picked this idea because the two halves of it just became available at the same time. Prediction markets got liquid enough on sports to be a real reference price, and their APIs are fully open — Polymarket's needs no authentication at all. Meanwhile the sports data needed to run a credible model (injuries, depth charts, play-by-play) is now free and well-maintained through open projects like nflverse. Two years ago you'd have needed a Sportradar contract to attempt this. Today one engineer can.

### How do you know people need what you're making?

**This is your weakest answer today and the single most important thing to fix in the next four weeks.** Do not write anything here you cannot defend. Partners push hardest on exactly this.

What to have by Oct 26, in descending order of value:

1. **A logged divergence that resolved your way.** One documented case — timestamps, screenshots — where your model moved on news and Kalshi or Polymarket took hours to follow. This is worth more than any number of survey responses because it proves the signal is real, not just that people say they'd like it.
2. **Retention on the digest.** Even 20-40 beta users with a week-two open rate. "N people, X% still opening in week 3."
3. **Direct conversations.** 10-15 talks with people active on Kalshi/Polymarket sports markets. Specific quotes beat paraphrase.

The structure to write it in once you have the data:

> *[N] people are on the divergence digest. [X%] still open it in week three. On [date], the model dropped [team] [N]% within [N] hours of the [injury/trade]; Kalshi didn't reprice until [N] hours later. [Quote from a user about what they did with that.]*

Placeholder honesty: if by Oct 26 you have users but no resolved divergence yet, say so plainly and give the retention number. Partners respect a founder who separates what they've proven from what they believe. They do not respect padding.

### Who writes code?

You do, all of it. Say so — solo technical founder who ships is a positive signal.

---

## Progress

### How far along are you?

Fill this in truthfully at submission. If you follow the engineering plan, by Oct 26 this reads roughly:

> Live at [url] since [date]. The simulation engine runs daily for [NFL/NBA]: 50,000 Monte Carlo season simulations, full playoff brackets, re-rated on injuries and transactions within [N] hours. It pulls live prices from Polymarket and Kalshi, computes the divergence, and pushes a digest when a gap crosses threshold. [N] beta users. [Traction sentence.]

### How long has each of you been working on this? Full-time?

Answer honestly. If it's nights and weekends, say that — and say what would make it full-time. YC funds people who will commit; they don't expect you to have quit already, but they want to know you will.

### Have you formed a legal entity? Company URL?

Probably no entity yet — that's fine and normal, it is not a negative. Get a URL live before applying even if it's one page; a link the partner can click is worth the hour it takes.

---

## Idea

### Who are your competitors? What do you understand about your business that they don't?

This is your strongest answer. The structure is that **everyone in the space has exactly half of the equation:**

| Who | Has | Missing |
|---|---|---|
| ESPN FPI / BPI, FiveThirtyEight-style models | An independent model | No market comparison — they never tell you the market is wrong |
| Polymarket, Kalshi | A live market price | No independent model — the price *is* their answer |
| Action Network, VSiN, Covers, tout services | Opinions and picks | No simulation, no calibration record, no market benchmark |
| Sportsbooks | Prices they set themselves | Structurally can't tell you their own number is off |

> Every one of them has a model or a price. Nobody publishes the *difference*. The difference is where all the information is: a model alone can't tell you if it's ahead of consensus, and a price alone can't tell you if it's stale. You need both sides to compute a signal, and no one is positioned to hold both.

**Be ready for the obvious pushback,** because a partner will raise it: *"Isn't that just what sharp bettors and quant shops already do privately?"*

The honest answer, which is also the better answer:

> Yes — and that's the validation, not the objection. People with capital build exactly this signal and keep it to themselves because they're trading on it. That proves the signal has value. What doesn't exist is the consumer version: the 99% of people following sports who will never build a Monte Carlo engine but would absolutely read a text that says the market hasn't priced tonight's injury yet. We're not competing with the quant shops. We're productizing what they already know works.

### How do or will you make money? How much could you make?

Subscription, and say clearly why you're *not* doing the obvious thing:

> Consumer subscription, roughly $15–20/month. We are deliberately not taking sportsbook or prediction-market affiliate revenue, even though it's the obvious money. Affiliate marketing for gambling operators triggers registration requirements in multiple states and reframes us from an analytics product into paid acquisition for a book. It also destroys the thing we're selling: nobody trusts a calibration record from a company paid per referral. Independence is the asset.
>
> Bottoms-up: tens of millions of Americans bet on sports or trade sports prediction markets. We don't need a large share — 100,000 subscribers at $18/month is roughly $21M ARR. Second line later is licensing the odds and calibration feed to media and fantasy platforms, which is cleaner revenue and doesn't compromise independence.

*(Replace "tens of millions" with a cited figure before submitting — a specific sourced number reads far better than a range, and partners check.)*

### What's new about what you're making?

> Two things became true recently and nobody has connected them yet. Prediction markets got liquid enough on sports that their prices are a meaningful reference, and their market data is fully open — Polymarket's requires no authentication and Kalshi's is free to read. At the same time, the sports data needed for a credible model went free and well-maintained. The result is that computing "the market is wrong about this team right now," continuously and publicly, became a one-engineer problem. It wasn't two years ago.

### If you had other ideas you considered, list them.

Answer honestly if you had others. If this is the one, say so — focus reads well. Don't invent alternatives to look prolific.

---

## Are you looking for a co-founder?

Per Section 9.10 of the PRD: yes, and be specific about what kind.

> Yes. The engineering is the part I'm covering — the simulation runs in under a second and the pipeline is the kind of system I've built for six years. The hard part is distribution in a saturated sports-content market. I'm looking for a co-founder who brings audience or consumer growth, not another backend engineer.

Naming your own gap accurately is a strength signal. Partners see a lot of technical founders who think distribution will sort itself out.

---

## The one-minute founder video

Partners watch this. It's short and most people waste it on biography.

**Don't** walk through your resume. **Do** this:

1. **(10s)** Who you are, one line. "I'm Kenny, I spent six years building backend infrastructure at YouTube, Microsoft, and Yahoo."
2. **(30s)** Show the product doing the thing. Screen-share an actual divergence: model here, Kalshi there, the gap, the alert. If you have a real resolved example, use that one — a concrete case where you were right first is the most persuasive thirty seconds available to you.
3. **(15s)** Why you'll win. The both-sides-of-the-equation point, in one sentence.
4. **(5s)** What you need. Honest ask.

Record it after the product is live, not before. A video showing a working thing beats a video describing a planned thing by a wide margin.

---

## Pre-submission checklist

- [ ] Phase 1 live and running daily
- [ ] At least one resolved divergence documented with timestamps
- [ ] Beta cohort with a real retention number
- [ ] One-page site live at a clickable URL
- [ ] Complete track record published — including losses (this is an FTC substantiation requirement per PRD 9.6, and it's also more persuasive than a clean one)
- [ ] Video recorded showing the live product
- [ ] Every number in the application traceable to something real
- [ ] Submit by **Sunday, Oct 26** (one week of buffer before the Nov 2 deadline)

---

## What will get you rejected

Worth internalizing, because these are the failure modes for this specific idea:

1. **No evidence of demand.** The most likely rejection reason. A spec plus enthusiasm loses to a live product with twelve engaged users.
2. **Sounding like a betting product.** You're building analytics with an independence thesis. If the application reads like a tout service, it gets sorted into a pile YC is cautious about. Lead with the model and the calibration record, not with picks.
3. **Overstated traction.** Partners verify in the interview. One inflated number costs you the whole application.
4. **Vague TAM.** "Sports betting is a $X billion market" is a phrase that makes partners stop reading. Bottoms-up subscriber math is better.
5. **No answer for "why won't ESPN just build this?"** Have one ready. The real answer: ESPN can't publish "the market is mispriced" without picking a fight with the sportsbooks it takes advertising money from. Structural conflict, not a capability gap. That's a good answer — use it.
