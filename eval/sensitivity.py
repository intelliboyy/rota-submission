"""Auto-fail guard: answers must change when the model's output changes."""
import json

from eval.common import load_data
from eval.mocks import GoldBackend, PerturbBackend
from rotasolve.cli import run_items
from rotasolve.llm import LLM


def main():
    items, _, _ = load_data()
    base, _ = run_items(items, "1x", LLM(GoldBackend(items)))
    for rel in ("BETWEEN", "STATION", "BEFORE"):
        alt, _ = run_items(items, "1x", LLM(PerturbBackend(items, rel)))
        changed = sum(json.dumps(base[i], sort_keys=True) != json.dumps(alt[i], sort_keys=True) for i in base)
        print(f"model stops reporting {rel:8s} -> {changed}/{len(items)} answers change")
        assert changed > 0, "answers do not depend on the model!"
    print("OK: answers depend on the model's output")


if __name__ == "__main__":
    main()
