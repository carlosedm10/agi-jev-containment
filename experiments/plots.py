from __future__ import annotations

import statistics
from collections import defaultdict

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    matplotlib = None
    plt = None

try:
    from . import analysis
except ImportError:
    import analysis

HERE = analysis.HERE


def exp_esc(chain):
    return analysis.chains.EXPECTED[chain][0]


def exp_lvl(chain):
    return analysis.chains.EXPECTED[chain][1]


def correct(chain, level):
    return (level >= 3) == exp_esc(chain) and level in exp_lvl(chain)


def load_models():
    jev = {}
    for r in analysis.load_rows("results.csv"):
        if r["mode"] == "lead" and int(r["k"]) == int(r["n_events"]):
            jev[r["chain"]] = analysis.lvl_num(r["choice"])

    helm = defaultdict(list)
    for r in analysis.load_rows("helmcode_results.csv"):
        if r["level"]:
            helm[r["model"]].append((r["chain"], int(r["level"])))

    chains_sorted = sorted(analysis.chains.EXPECTED,
                           key=lambda c: (min(exp_lvl(c)), c))
    models = {"jev": [(c, jev[c]) for c in chains_sorted if c in jev]}
    models.update(helm)
    return chains_sorted, models


def plot_accuracy(models):
    acc = {}
    for m, preds in models.items():
        hits = [correct(c, l) for c, l in preds]
        acc[m] = sum(hits) / len(hits) if hits else 0

    order = sorted(acc, key=lambda m: acc[m], reverse=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(order, [acc[m] for m in order], color="steelblue")
    ax.bar_label(bars, fmt="%.0f%%", labels=[f"{acc[m]:.0%}" for m in order])
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("accuracy (level in range + escalate correct)")
    ax.set_title("Full-chain verdict accuracy vs ground truth")
    fig.tight_layout()
    fig.savefig(HERE / "plot_accuracy.png", dpi=150)


def plot_levels(chains_sorted, models):
    fig, ax = plt.subplots(figsize=(11, 5))
    w = 0.8 / len(models)
    for i, (m, preds) in enumerate(models.items()):
        got = dict(preds)
        xs = [x + i * w for x in range(len(chains_sorted))]
        ax.bar(xs, [got.get(c, 0) for c in chains_sorted], width=w, label=m)

    for x, c in enumerate(chains_sorted):
        lo, hi = min(exp_lvl(c)), max(exp_lvl(c))
        ax.bar(x + 0.4, hi - lo + 1, bottom=lo - 0.5, width=0.8,
               color="grey", alpha=0.25, zorder=0)

    ax.set_xticks([x + 0.4 for x in range(len(chains_sorted))], chains_sorted, rotation=20)
    ax.set_yticks(range(1, 6), [f"{i} {analysis.LEVEL_NAMES[i]}" for i in range(1, 6)])
    ax.set_ylim(0.5, 5.5)
    ax.set_title("Predicted level per chain (grey band = expected range)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / "plot_levels.png", dpi=150)


def plot_latency():
    lat = defaultdict(list)
    tps = defaultdict(list)
    for r in analysis.load_rows("helmcode_results.csv"):
        if r["latency_s"]:
            lat[r["model"]].append(float(r["latency_s"]))
        if r.get("tok_per_s"):
            tps[r["model"]].append(float(r["tok_per_s"]))
    for r in analysis.load_rows("results.csv"):
        if r.get("latency_s"):
            lat["jev"].append(float(r["latency_s"]))
        if r.get("tok_per_s"):
            tps["jev"].append(float(r["tok_per_s"]))

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


def main():
    if plt is None:
        raise RuntimeError("matplotlib is required to render plots")
    chains_sorted, models = load_models()
    plot_accuracy(models)
    plot_levels(chains_sorted, models)
    plot_latency()
    print("wrote plot_accuracy.png, plot_levels.png, plot_latency.png")


if __name__ == "__main__":
    main()
