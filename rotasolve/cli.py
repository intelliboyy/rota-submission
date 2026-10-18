import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from .llm import make_llm
from .pipeline import BUDGETS, Config, flat_config, solve_item

FALLBACK = {"case": "unique", "assignment": {}}


def run_items(items, budget, llm, cfg=None, workers=4):
    cfg = cfg or Config()

    def one(item):
        try:
            return item["id"], *solve_item(item, budget, llm, cfg)
        except Exception as e:   # never lose an item; the answer is simply wrong
            print(f"[warn] {item['id']}: {e!r}", file=sys.stderr)
            return item["id"], dict(FALLBACK), {"error": repr(e), "calls": 0}

    answers, infos = {}, {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for iid, ans, info in ex.map(one, items):
            answers[iid], infos[iid] = ans, info
    return answers, infos


def audit(infos, budget):
    cap = BUDGETS[budget]
    calls = [i.get("calls", 0) for i in infos.values()]
    bad = [k for k, i in infos.items() if not (1 <= i.get("calls", 0) <= cap)]
    print(f"[budget {budget}] calls/item min={min(calls)} max={max(calls)} "
          f"mean={sum(calls) / len(calls):.2f}  violations={len(bad)}", file=sys.stderr)
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(prog="run")
    ap.add_argument("items")
    ap.add_argument("--budget", required=True, choices=list(BUDGETS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--relax", action="store_true", help="experimental minimal-edit fallback")
    ap.add_argument("--no-repair", action="store_true")
    ap.add_argument("--no-vote", action="store_true", help="1 extraction, rest spent on repair")
    ap.add_argument("--no-bias", action="store_true", help="omit the per-section base-rate hint")
    ap.add_argument("--flat", action="store_true", help="old single-section prompt (ablation)")
    ap.add_argument("--log", help="jsonl call log")
    ap.add_argument("--debug-out", help="per-item diagnostics json")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)

    items = json.load(open(a.items))
    if a.limit:
        items = items[:a.limit]
    cfg = (flat_config if a.flat else Config)(repair=not a.no_repair, relax=a.relax, bias=not a.no_bias)
    if a.no_vote:
        cfg.plans = {k: [v[0]] for k, v in cfg.plans.items()}
    llm = make_llm(a.log)
    answers, infos = run_items(items, a.budget, llm, cfg, a.workers)

    tmp = a.out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(answers, f, indent=2)
    os.replace(tmp, a.out)
    if a.debug_out:
        json.dump(infos, open(a.debug_out, "w"), indent=2)
    bad = audit(infos, a.budget)
    print(f"wrote {a.out} ({len(answers)} items)", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
