"""Full system at 1x / 3x / 10x. Writes eval/final_check.md.

    python -m eval.final_check --runs 3
"""
import argparse
import statistics as st

from eval.common import ROOT, load_data
from eval.mocks import NoisyBackend
from rotasolve.cli import run_items
from rotasolve.llm import LLM, make_llm
from rotasolve.pipeline import BUDGETS, Config

CASES = ("unique", "ambiguous", "inconsistent")


def fmt_conf(conf):
    lines = ["true \\ declared | unique | ambiguous | inconsistent",
             "---|---:|---:|---:"]
    for t in CASES:
        row = conf[t]
        lines.append(f"{t} | {row['unique']} | {row['ambiguous']} | {row['inconsistent']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--mock", choices=["noisy"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budgets", nargs="+", default=list(BUDGETS))
    a = ap.parse_args()
    items, key, sc = load_data(a.data)
    cfg = Config()

    parts = [f"# Final check ({a.runs} run{'s' if a.runs != 1 else ''})\n",
             "| budget | macro exact match | unique | ambiguous | inconsistent | budget violations |",
             "|---|---:|---:|---:|---:|---:|"]
    last_conf = {}
    for b in a.budgets:
        scores, rates, viol, confs = [], {c: [] for c in CASES}, 0, []
        for r in range(a.runs):
            llm = LLM(NoisyBackend(items, seed=r)) if a.mock else make_llm()
            ans, infos = run_items(items, b, llm, cfg, a.workers)
            viol += sum(1 for i in infos.values() if not 1 <= i.get("calls", 0) <= BUDGETS[b])
            res = sc.score(key, ans, items)
            scores.append(res["macro_exact_match"])
            for c in CASES:
                rates[c].append(res["per_case_rate"][c])
            confs.append(res["confusion"])
        sd = st.pstdev(scores) if len(scores) > 1 else 0.0
        cell = f"{100 * st.mean(scores):.1f}% ±{100 * sd:.1f}"
        per = " | ".join(f"{100 * st.mean(rates[c]):.1f}%" for c in CASES)
        parts.append(f"| {b} | {cell} | {per} | {viol} |")
        last_conf[b] = confs[-1]

    parts.append(f"\nmacro exact match on the visible set, mean ±sd over {a.runs} runs"
                 + (" (MOCK reader: machinery check only)" if a.mock else "") + "\n")
    for b, conf in last_conf.items():
        parts.append(f"## {b} confusion (last run)\n")
        parts.append(fmt_conf(conf))
        parts.append("")
    md = "\n".join(parts) + "\n"
    open(f"{ROOT}/eval/final_check.md", "w").write(md)
    print(md)


if __name__ == "__main__":
    main()
