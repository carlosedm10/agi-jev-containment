"""Compare jev vs Helmcode supervisor models on the same chains.

jev:    results.csv  -> verdict at mode=lead, k=n_events (full chain)
models: helmcode_results.csv -> suspected_level per chain

Out: experiments/plot_accuracy.png, experiments/plot_levels.png
"""

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
from helmcode_bench import EXPECTED  # noqa: E402

HERE = Path(__file__).parent
LEVELS = {1: "mild", 2: "moderate", 3: "severe", 4: "critical", 5: "catastrophic"}

# level name -> int, e.g. "level_3_severe" -> 3
def lvl_num(name):
    return int(name.split("_")[1]) if isinstance(name, str) else name


def exp_esc(chain):  return EXPECTED[chain][0]
def exp_lvl(chain):  return EXPECTED[chain][1]


def correct(chain, level):
    return (level >= 3) == exp_esc(chain) and level in exp_lvl(chain)


# --- load -------------------------------------------------------------------

# jev: full-chain verdicts
jev = {}
with (HERE / "results.csv").open() as f:
    for r in csv.DictReader(f):
        if r["mode"] == "lead" and int(r["k"]) == int(r["n_events"]):
            jev[r["chain"]] = lvl_num(r["choice"])

# helmcode: per model, list of (chain, level) per rep
helm = defaultdict(list)
with (HERE / "helmcode_results.csv").open() as f:
    for r in csv.DictReader(f):
        if r["level"] != "":
            helm[r["model"]].append((r["chain"], int(r["level"])))

chains = sorted(EXPECTED, key=lambda c: (min(exp_lvl(c)), c))
models = {"jev": [(c, jev[c]) for c in chains if c in jev]}
models.update({m: v for m, v in helm.items()})

# --- fig 1: overall accuracy, sorted ----------------------------------------

acc = {}
for m, preds in models.items():
    hits = [correct(c, l) for c, l in preds]
    acc[m] = sum(hits) / len(hits) if hits else 0

order = sorted(acc, key=acc.get, reverse=True)
fig, ax = plt.subplots(figsize=(7, 4))
bars = ax.bar(order, [acc[m] for m in order], color="steelblue")
ax.bar_label(bars, fmt="%.0f%%", labels=[f"{acc[m]:.0%}" for m in order])
ax.set_ylim(0, 1.15)
ax.set_ylabel("accuracy (level in range + escalate correct)")
ax.set_title("Full-chain verdict accuracy vs ground truth")
fig.tight_layout()
fig.savefig(HERE / "plot_accuracy.png", dpi=150)

# --- fig 2: predicted level per chain, grouped bars -------------------------

fig, ax = plt.subplots(figsize=(11, 5))
w = 0.8 / len(models)
for i, (m, preds) in enumerate(models.items()):
    got = dict(preds)
    xs = [x + i * w for x in range(len(chains))]
    ax.bar(xs, [got.get(c, 0) for c in chains], width=w, label=m)

# expected range as grey band behind the group
for x, c in enumerate(chains):
    lo, hi = min(exp_lvl(c)), max(exp_lvl(c))
    ax.bar(x + 0.4, hi - lo + 1, bottom=lo - 0.5, width=0.8,
           color="grey", alpha=0.25, zorder=0)

ax.set_xticks([x + 0.4 for x in range(len(chains))], chains, rotation=20)
ax.set_yticks(range(1, 6), [f"{i} {LEVELS[i]}" for i in range(1, 6)])
ax.set_ylim(0.5, 5.5)
ax.set_title("Predicted level per chain (grey band = expected range)")
ax.legend()
fig.tight_layout()
fig.savefig(HERE / "plot_levels.png", dpi=150)

# --- fig 3: latency + tok/s, sorted -----------------------------------------

lat = defaultdict(list)
tps = defaultdict(list)
with (HERE / "helmcode_results.csv").open() as f:
    for r in csv.DictReader(f):
        if r["latency_s"]:
            lat[r["model"]].append(float(r["latency_s"]))
        if r["tok_per_s"]:
            tps[r["model"]].append(float(r["tok_per_s"]))
# jev joins once results.csv has a latency_s column
try:
    with (HERE / "results.csv").open() as f:
        for r in csv.DictReader(f):
            if r.get("latency_s"):
                lat["jev"].append(float(r["latency_s"]))
            if r.get("tok_per_s"):
                tps["jev"].append(float(r["tok_per_s"]))
except KeyError:
    pass

order = sorted(lat, key=lambda m: statistics.mean(lat[m]))
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
b1 = a1.bar(order, [statistics.mean(lat[m]) for m in order],
            yerr=[statistics.stdev(lat[m]) if len(lat[m]) > 1 else 0 for m in order],
            capsize=4, color="steelblue")
a1.bar_label(b1, fmt="%.2fs")
a1.set_title("Mean latency per call (sorted)")
a2.bar(order, [statistics.mean(tps.get(m, [0])) for m in order], color="seagreen")
for i, m in enumerate(order):
    a2.text(i, statistics.mean(tps.get(m, [0])), f"{statistics.mean(tps.get(m, [0])):.0f}",
            ha="center", va="bottom")
a2.set_title("Mean output tok/s")
fig.tight_layout()
fig.savefig(HERE / "plot_latency.png", dpi=150)

print("wrote plot_accuracy.png, plot_levels.png, plot_latency.png")
