"""
How much Monte Carlo precision does the product actually need?

Two things drive the answer:
  1. Single-outcome odds (championship %) — modest precision needed.
  2. Parlay combined probability — relative errors of each leg COMPOUND,
     so the longshot tier is far more sensitive than a single pick.
"""

import numpy as np


def se(p, n):
    return np.sqrt(p * (1 - p) / n)


def parlay_error(legs, n):
    """Relative and absolute error of a multiplied parlay probability."""
    legs = np.array(legs, dtype=float)
    rel = np.sqrt(np.sum((se(legs, n) / legs) ** 2))
    combined = legs.prod()
    return combined, rel, combined * rel


print("=" * 72)
print("SINGLE OUTCOME: standard error on a championship probability")
print("=" * 72)
print(f"{'true p':>8} " + "".join(f"{f'n={n:,}':>14}" for n in (1_000, 10_000, 50_000)))
for p in (0.40, 0.15, 0.05, 0.01):
    row = f"{p:>7.0%} "
    for n in (1_000, 10_000, 50_000):
        s = se(p, n)
        row += f"  ±{s:>5.2%} ({s/p:>4.0%})"
    print(row)

print()
print("=" * 72)
print("PARLAY: combined probability error (relative errors compound)")
print("=" * 72)

scenarios = {
    "Safe (2 legs @ 80%, 75%)": [0.80, 0.75],
    "Safe (3 legs @ 75%, 70%, 68%)": [0.75, 0.70, 0.68],
    "Balanced (3 legs @ 60%, 55%, 52%)": [0.60, 0.55, 0.52],
    "Balanced (4 legs @ 58%, 55%, 50%, 48%)": [0.58, 0.55, 0.50, 0.48],
    "Long shot (4 legs @ 25%, 20%, 15%, 10%)": [0.25, 0.20, 0.15, 0.10],
    "Long shot (5 legs @ 20%, 18%, 15%, 12%, 8%)": [0.20, 0.18, 0.15, 0.12, 0.08],
}

for label, legs in scenarios.items():
    print(f"\n{label}")
    for n in (1_000, 10_000, 50_000):
        combined, rel, abs_err = parlay_error(legs, n)
        odds = 1 / combined
        lo = 1 / (combined + abs_err)
        hi = 1 / (combined - abs_err)
        print(f"   n={n:>6,}  P={combined:>7.3%}  rel err ±{rel:>5.1%}   "
              f"→ '1 in {odds:,.0f}'  but really 1 in {lo:,.0f} – {hi:,.0f}")

print()
print("=" * 72)
print("COST OF PRECISION (from measured benchmark: ~0.32s for both")
print("leagues at 50k sims on 2 cores)")
print("=" * 72)
measured_50k_both_leagues_sec = 0.324
for n in (1_000, 10_000, 50_000, 200_000):
    t = measured_50k_both_leagues_sec * n / 50_000
    print(f"  {n:>7,} sims/league → {t:>6.3f}s per full refresh, "
          f"{t*30/60:>5.2f} min/month of CPU if run daily")
