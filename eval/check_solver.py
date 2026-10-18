"""Gold labels -> solver -> official scorer.  Must give macro 1.0 at 1x with 1 call/item."""
import argparse
import json

from eval.common import load_data
from eval.mocks import GoldBackend
from rotasolve.cli import audit, run_items
from rotasolve.llm import LLM
from rotasolve.pipeline import Config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    a = ap.parse_args()
    items, key, sc = load_data(a.data)
    llm = LLM(GoldBackend(items))
    answers, infos = run_items(items, "1x", llm, Config())
    audit(infos, "1x")
    res = sc.score(key, answers, items)
    res.pop("per_item")
    print(json.dumps({k: res[k] for k in ("macro_exact_match", "per_case_rate", "confusion")}, indent=1))
    return 0 if res["macro_exact_match"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
