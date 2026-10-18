"""Ablation table: component on/off x budget, N runs each, official scorer.

    python -m eval.ablate --rows A B B2 B3 C C3 D --runs 2
    python -m eval.ablate --mock noisy --runs 1    # dry run of the machinery only

Writes eval/ablation.md and eval/ablation.csv.  Also checks the call budget on
every run.  Numbers from --mock say nothing about Granite.

Rows A, B, B2 and B3 are one-pass configs: the 3x and 10x cells are the same
configuration as 1x, so those numbers should match across budgets.
"""
import argparse
import csv
import statistics as st

from eval.common import ROOT, load_data
from eval.mocks import NoisyBackend
from rotasolve.cli import run_items
from rotasolve.llm import LLM, make_llm
from rotasolve.pipeline import BUDGETS, MULTIVIEW_PLANS, Config, flat_config

ONE = {"1x": ["STPM"], "3x": ["STPM"], "10x": ["STPM"]}
ROWS = {
    "A":  ("A flat prompt, 1 pass",
           flat_config(repair=False, conf_core=False, plans=dict(ONE))),
    "B":  ("B + routed sections (1 pass)",
           Config(plans=dict(ONE), repair=False, conf_core=False)),
    "B2": ("B2 routed, no base-rate hint (1 pass)",
           Config(plans=dict(ONE), repair=False, conf_core=False, bias=False)),
    "B3": ("B3 routed, no demonstrations (1 pass)",
           Config(plans=dict(ONE), repair=False, conf_core=False, examples=False)),
    "C":  ("C + votes (budget plan)",
           Config(repair=False, conf_core=True)),
    "C2": ("C2 multi-view plan instead of repeats",
           Config(plans={k: list(v) for k, v in MULTIVIEW_PLANS.items()},
                  focus_weight=1.5, repair=False)),
    "C3": ("C3 majority-only acceptance (accept=0.5)",
           Config(accept={"1x": 0.5, "3x": 0.5, "10x": 0.5}, repair=False)),
    "D":  ("D + solver-guided repair (full)",
           Config(repair=True, conf_core=True)),
    "E":  ("E flat prompt, repeated votes + repair",
           flat_config(repair=True, conf_core=True)),
    "F":  ("F D + minimal-edit relax (experimental)",
           Config(repair=True, conf_core=True, relax=True)),
}
DEFAULT_ROWS = ["A", "B", "B2", "B3", "C", "C3", "D"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--mock", choices=["noisy"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budgets", nargs="+", default=list(BUDGETS))
    ap.add_argument("--rows", nargs="+", default=DEFAULT_ROWS,
                    help="row ids to run (default: A B B2 B3 C C3 D)")
    a = ap.parse_args()
    unknown = [r for r in a.rows if r not in ROWS]
    if unknown:
        raise SystemExit(f"unknown --rows {unknown}; known: {', '.join(ROWS)}")
    items, key, sc = load_data(a.data)

    table, rows_csv = [], []
    for rid in a.rows:
        name, cfg = ROWS[rid]
        cells = []
        for b in a.budgets:
            scores, viol = [], 0
            for r in range(a.runs):
                llm = LLM(NoisyBackend(items, seed=r)) if a.mock else make_llm()
                ans, infos = run_items(items, b, llm, cfg, a.workers)
                viol += sum(1 for i in infos.values() if not 1 <= i.get("calls", 0) <= BUDGETS[b])
                res = sc.score(key, ans, items)
                scores.append(res["macro_exact_match"])
                rows_csv.append([rid, name, b, r, res["macro_exact_match"],
                                 *[res["per_case_rate"][c] for c in ("unique", "ambiguous", "inconsistent")],
                                 viol])
            sd = st.pstdev(scores) if len(scores) > 1 else 0.0
            cells.append(f"{100 * st.mean(scores):.1f}% ±{100 * sd:.1f}"
                         + (f" (budget violations: {viol})" if viol else ""))
        table.append((rid, name, cells))
    hdr = "| id | component | " + " | ".join(a.budgets) + " | runs |\n|---|---|---|" + "---|" * len(a.budgets)
    body = "\n".join(f"| {rid} | {n} | " + " | ".join(c) + f" | {a.runs} |" for rid, n, c in table)
    md = (f"{hdr}\n{body}\n\nmacro exact match on the visible set, mean ±sd over {a.runs} runs"
          + (" (MOCK reader: machinery check only)" if a.mock else "") + "\n")
    open(f"{ROOT}/eval/ablation.md", "w").write(md)
    with open(f"{ROOT}/eval/ablation.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "row", "budget", "run", "macro", "unique", "ambiguous", "inconsistent", "budget_violations"])
        w.writerows(rows_csv)
    print(md)


if __name__ == "__main__":
    main()
