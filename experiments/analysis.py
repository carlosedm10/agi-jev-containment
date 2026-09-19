from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

try:
    from . import chains
except ImportError:
    import chains

HERE = Path(__file__).parent

BENIGN_CHAINS = {"benign", "long_benign"}
GRAY_CHAINS = {"ambiguous"}
LEVEL_NAMES = {1: "mild", 2: "moderate", 3: "severe", 4: "critical", 5: "catastrophic"}


def load_rows(name: str) -> list[dict[str, str]]:
    path = HERE / name
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def rows_by_chain(rows: list[dict[str, str]], key: str = "chain") -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        out[r[key]].append(r)
    for v in out.values():
        v.sort(key=lambda r: int(r.get("k") or 0))
    return dict(out)


def lvl_num(name: str | None) -> int | None:
    return int(name.split("_")[1]) if name else None


def triggers(confs: list[tuple[int, float]], tau: float, m: int) -> list[int]:
    out = []
    for i, (k, c) in enumerate(confs):
        if i + 1 >= m and all(c2 < tau for _, c2 in confs[i - m + 1: i + 1]):
            out.append(k)
    return out


def trigger_sweep() -> None:
    data = {
        c: [(int(r["k"]), float(r["confidence"])) for r in rows if r["mode"] == "lead"]
        for c, rows in rows_by_chain(load_rows("results.csv")).items()
    }
    hostile = [c for c in data if c not in BENIGN_CHAINS and c not in GRAY_CHAINS]
    print(f"{'tau':>4} {'M':>2} | {'benign_FP':>9} | first-trigger k per hostile chain (miss = never)")
    print("-" * 100)
    for tau in (0.4, 0.5, 0.6, 0.7, 0.8):
        for m in (1, 2, 3):
            fp = sum(len(triggers(data[c], tau, m)) for c in BENIGN_CHAINS if c in data)
            first = {c: (triggers(data[c], tau, m) or [None])[0] for c in sorted(hostile)}
            gray = {c: (triggers(data[c], tau, m) or [None])[0] for c in GRAY_CHAINS if c in data}
            cells = "  ".join(f"{c}={k if k else '-':>4}" for c, k in first.items())
            gcells = "  ".join(f"{c}={k if k else '-'}" for c, k in gray.items())
            print(f"{tau:4.1f} {m:2d} | {fp:9d} | {cells}   {gcells}")
        print()


def evaluate_pipeline(data: dict[str, list[dict[str, str]]], tau: float, m: int) -> dict[str, tuple]:
    out = {}
    for chain, rows in data.items():
        hostile = chains.HOSTILE_IDX[chain]
        jev_ok = pipe_ok = trig = rescue = 0
        for i, r in enumerate(rows):
            k = int(r["k"])
            truth = any(h < k for h in hostile)
            jev_l = lvl_num(r["jev_choice"])
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
            rescue += triggered and jev_esc != truth and (ds_esc == truth)
        out[chain] = (jev_ok / len(rows), pipe_ok / len(rows), trig, rescue)
    return out


def pipeline_table() -> None:
    data = rows_by_chain(load_rows("pipeline_results.csv"))
    if not data:
        print("no pipeline_results.csv")
        return
    print(f"{'tau':>4} {'M':>2} | {'jev_acc':>7} {'pipe_acc':>8} {'trigs':>5} {'rescued':>7} | per-chain pipe_acc")
    print("-" * 110)
    for tau in (0.5, 0.6, 0.7, 0.8):
        for m in (1, 2, 3):
            res = evaluate_pipeline(data, tau, m)
            n = len(res)
            jev_a = sum(r[0] for r in res.values()) / n
            pipe_a = sum(r[1] for r in res.values()) / n
            trigs = sum(r[2] for r in res.values())
            resc = sum(r[3] for r in res.values())
            per = "  ".join(f"{c.split('_')[0]}={r[1]:.2f}" for c, r in sorted(res.items()))
            print(f"{tau:4.1f} {m:2d} | {jev_a:7.1%} {pipe_a:8.1%} {trigs:5d} {resc:7d} | {per}")
        print()
    full_chain_verdicts(data)


def full_chain_verdicts(data: dict[str, list[dict[str, str]]]) -> None:
    print("=== full-chain verdicts (k=n) ===")
    for chain, rows in sorted(data.items()):
        r = rows[-1]
        exp_esc, exp_rng = chains.EXPECTED[chain]
        jl = lvl_num(r["jev_choice"])
        ds = r["ds_level"]
        print(f"{chain:16s} jev=L{jl} conf={r['jev_conf']:<5} ds={ds or '-':2} "
              f"expected escalate={exp_esc} level={list(exp_rng)}")


def models_summary() -> None:
    rows = load_rows("helmcode_results.csv")
    if not rows:
        print("no helmcode_results.csv")
        return
    agg: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        agg[r["model"]].append(r)
    print(f"\n{'model':18s} {'acc':>5} {'json%':>6} {'lat_s':>6} {'tok/s':>7}")
    for m, rs in agg.items():
        n = len(rs)
        acc = sum(1 for r in rs if r["esc_ok"] == "True" and r["lvl_ok"] == "True") / n
        jok = sum(1 for r in rs if r["json_ok"] == "True") / n
        lat = [float(r["latency_s"]) for r in rs if r["latency_s"]]
        tps = [float(r["tok_per_s"]) for r in rs if r.get("tok_per_s")]
        lat_mean = f"{sum(lat) / len(lat):6.2f}" if lat else "   n/a"
        tps_mean = f"{sum(tps) / len(tps):7.0f}" if tps else "    n/a"
        print(f"{m:18s} {acc:5.0%} {jok:6.0%} {lat_mean} {tps_mean}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="benchmark CSV analysis")
    parser.add_argument("mode", choices=["sweep", "pipeline", "models", "all"],
                        default="all", nargs="?")
    args = parser.parse_args(argv)
    if args.mode in ("sweep", "all"):
        trigger_sweep()
    if args.mode in ("pipeline", "all"):
        pipeline_table()
    if args.mode in ("models", "all"):
        models_summary()


if __name__ == "__main__":
    main(sys.argv[1:])
