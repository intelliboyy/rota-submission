"""Raw one-shot baseline (no harness): ask the model for the answer JSON directly."""
import json
import re

from eval.common import ROOT, load_data
from rotasolve.llm import ItemBudget, make_llm

FORMAT = """Answer with JSON only, in exactly one of these forms.
{"case":"unique","assignment":{"<name>":{"block":"HH:MM","station":"<station>"}}}
{"case":"ambiguous","assignments":[{...},{...}]}
{"case":"inconsistent","conflicts":["<statement copied verbatim>", "..."]}
Give "station" only for people on a station. Name every person on the rota."""


def main():
    items, key, sc = load_data()
    llm = make_llm()
    answers = {}
    for it in items:
        msgs = [{"role": "user", "content": it["text"] + "\n\n" + FORMAT}]
        text = llm.complete(ItemBudget(it["id"], 1), msgs, tag="baseline")
        m = re.search(r"\{.*\}", text, re.S)
        try:
            answers[it["id"]] = json.loads(m.group(0)) if m else {}
        except Exception:
            answers[it["id"]] = {}
    res = sc.score(key, answers, items)
    print("raw one-shot macro:", res["macro_exact_match"], res["per_case_rate"])


if __name__ == "__main__":
    main()
