"""Where does extraction lose points?  One extraction call per item.

Writes eval/extraction_report.md (tables), eval/extraction_errors.md (every wrong
line: gold vs predicted vs the line text) and eval/extraction_sample.txt (raw
model output for the first items).  Use --mock noisy for a dry run.
"""
import argparse
import re
from collections import Counter

from eval.common import ROOT, load_data
from eval.gold import gold_constraints
from eval.mocks import NoisyBackend
from rotasolve.extract import filter_allowed, parse_detailed
from rotasolve.llm import LLM, ItemBudget, make_llm
from rotasolve.parse import parse_item
from rotasolve.prompt import build_messages
from rotasolve.route import route
from rotasolve.schema import fmt

NEAR = re.compile(r"\d\d:\d\d|intake|calibration|packing", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--mock", choices=["noisy"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--bias", choices=["on", "off"], default="on")
    ap.add_argument("--prompt", choices=["routed", "flat"], default="routed")
    a = ap.parse_args()
    items, _, _ = load_data(a.data)
    items = items[:a.limit] if a.limit else items
    llm = LLM(NoisyBackend(items)) if a.mock else make_llm()

    tp, fn, wrong = Counter(), Counter(), Counter()
    status = Counter()           # per asked line: ok / none / invalid / unparsed / missing
    gold_status = Counter()      # what happened to lines that ARE constraints
    fp_near = fp_pure = n_near = n_pure = items_exact = 0
    errors, samples = [], []
    for it in items:
        rota = parse_item(it)
        gold = gold_constraints(rota)
        ids = list(range(len(rota.lines)))
        text = llm.complete(ItemBudget(it["id"], 1), build_messages(rota, ids, a.prompt == "routed", a.bias == "on"))
        if len(samples) < 2:
            samples.append(f"##### {it['id']}\n{text}\n")
        det = parse_detailed(text, rota, set(ids))
        if a.prompt == "routed":
            det = filter_allowed(det, rota)
        ok_item = True
        for i in ids:
            skipped = a.prompt == "routed" and route(rota.lines[i], rota) == "Z"
            st, pred = ("skipped", None) if skipped else det.get(i, ("missing", None))
            status[st] += 1
            g = gold.get(i)
            if g:
                gold_status[st] += 1
                if pred == g:
                    tp[g[0]] += 1
                else:
                    ok_item = False
                    (fn if pred is None else wrong)[g[0]] += 1
                    errors.append((g[0], f"[{st}] gold={fmt(g)} pred={fmt(pred) if pred else '-'} | {rota.lines[i]}"))
            else:
                near = bool(NEAR.search(rota.lines[i]))
                n_near += near; n_pure += (not near)
                if pred is not None:
                    fp_near += near; fp_pure += (not near); ok_item = False
                    errors.append(("FALSE+", f"[{st}] pred={fmt(pred)} (line asserts nothing) | {rota.lines[i]}"))
        items_exact += ok_item

    rels = sorted(set(tp) | set(fn) | set(wrong))
    out = ["| relation | correct | missed (said NONE/no vote) | wrong args or direction | recall |", "|---|---|---|---|---|"]
    for r in rels:
        t = tp[r] + fn[r] + wrong[r]
        out.append(f"| {r} | {tp[r]} | {fn[r]} | {wrong[r]} | {tp[r] / t:.2f} |")
    T = sum(tp.values()); tot = T + sum(fn.values()) + sum(wrong.values())
    out += ["", f"- overall line recall on real constraints: {T}/{tot} = {T / tot:.3f}",
            f"- what happened to the {tot} real-constraint lines: {dict(gold_status)}",
            f"- all lines by outcome: {dict(status)}  (invalid = relation/names rejected by validation; unparsed = no relation(...) found; disallowed = relation not allowed in that note's section; missing = line not answered; skipped = routed to Z, never sent, counts as NONE)",
            f"- false positives on near-miss lines: {fp_near}/{n_near}; on pure filler: {fp_pure}/{n_pure}",
            f"- items with every line right: {items_exact}/{len(items)}"]
    open(f"{ROOT}/eval/extraction_report.md", "w").write("\n".join(out) + "\n")
    errors.sort(key=lambda e: e[0])
    open(f"{ROOT}/eval/extraction_errors.md", "w").write("\n".join(f"{r}: {m}" for r, m in errors) + "\n")
    open(f"{ROOT}/eval/extraction_sample.txt", "w").write("\n".join(samples))
    print("\n".join(out))
    print("\nwrote eval/extraction_report.md, eval/extraction_errors.md, eval/extraction_sample.txt")


if __name__ == "__main__":
    main()
