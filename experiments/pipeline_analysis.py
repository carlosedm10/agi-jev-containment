"""Analyze the two-tier pipeline: jev alone vs jev + deepseek on low conf.

Per-window ground truth: does the window contain any hostile event?
Sweep (tau, M): trigger = conf < tau for M consecutive evals. When triggered,
the pipeline uses deepseek's verdict (if its JSON parsed), else jev's.

Run: python experiments/pipeline_analysis.py
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jev_pipeline_bench import EXPECTED, HOSTILE_IDX  # noqa: E402

HERE = Path(__file__).parent

def lvl(name):
    return int(name.split("_")[1]) if name else None

# chain -> sorted rows
data = defaultdict(list)
with (HERE / "pipeline_results.csv").open() as f:
    for r in csv.DictReader(f):
        data[r["chain"]].append(r)
for v in data.values():
    v.sort(key=lambda r: int(r["k"]))


def evaluate(tau, m):
    """Returns per-chain (jev_acc, pipe_acc, n_triggers, rescue_count)."""
    out = {}
    for chain, rows in data.items():
        hostile = HOSTILE_IDX[chain]
        jev_ok = pipe_ok = trig = rescue = 0
        for i, r in enumerate(rows):
            k = int(r["k"])
            truth = any(h < k for h in hostile)          # hostile already happened?
            jev_l = lvl(r["jev_choice"])
            jev_esc = jev_l is not None and jev_l >= 3
            triggered = (
                i + 1 >= m
                and all(rows[j]["jev_conf"] != "" and float(rows[j]["jev_conf"]) < tau
                        for j in range(i - m + 1, i + 1))
            )
            if triggered:
                trig += 1
            ds_esc = r["ds_escalate"] == "True" if r["ds_escalate"] != "" else None
            pipe_esc = ds_esc if (triggered and ds_esc is not None) else jev_esc
            jev_ok += jev_esc == truth
            pipe_ok += pipe_esc == truth
            rescue += triggered and not (jev_esc == truth) and (ds_esc == truth)
        out[chain] = (jev_ok / len(rows), pipe_ok / len(rows), trig, rescue)
    return out


print(f"{'tau':>4} {'M':>2} | {'jev_acc':>7} {'pipe_acc':>8} {'trigs':>5} {'rescued':>7} | per-chain pipe_acc")
print("-" * 110)
for tau in (0.5, 0.6, 0.7, 0.8):
    for m in (1, 2, 3):
        res = evaluate(tau, m)
        n = len(res)
        jev_a = sum(r[0] for r in res.values()) / n
        pipe_a = sum(r[1] for r in res.values()) / n
        trigs = sum(r[2] for r in res.values())
        resc = sum(r[3] for r in res.values())
        per = "  ".join(f"{c.split('_')[0]}={r[1]:.2f}" for c, r in sorted(res.items()))
        print(f"{tau:4.1f} {m:2d} | {jev_a:7.1%} {pipe_a:8.1%} {trigs:5d} {resc:7d} | {per}")
    print()

# full-chain verdict comparison (k = n_events)
print("=== full-chain verdicts (lead, k=n) ===")
for chain, rows in data.items():
    r = rows[-1]
    exp_esc, exp_rng = EXPECTED[chain]
    jl = lvl(r["jev_choice"])
    ds = r["ds_level"]
    print(f"{chain:16s} jev=L{jl} conf={r['jev_conf']:<5} ds={ds or '-':2} "
          f"expected escalate={exp_esc} level={list(exp_rng)}")
