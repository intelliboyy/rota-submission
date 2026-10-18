"""One model call -> {line_id: constraint | None} for the lines asked about."""
import re

from .prompt import build_messages
from .route import ALLOWED, route
from .schema import canon

LINE_RE = re.compile(r"^\s*L\s*(\d+)\s*[:.)\-]\s*(.+?)\s*$", re.M | re.I)
CALL_RE = re.compile(r"\b([A-Za-z_]+)\s*\(([^()]*)\)")


def parse_detailed(text, rota, wanted):
    """{line: (status, constraint)}; status in none | ok | invalid | unparsed.

    A line absent from the result was not answered at all.  The call may be
    followed by trailing words ("AT(Kai, 09:00) because ..."); the first
    relation(...) in the line is used.
    """
    out = {}
    for m in LINE_RE.finditer(text or ""):
        k = int(m.group(1)) - 1
        if k not in wanted or k in out:
            continue
        body = m.group(2).strip().strip("`*")
        if body.upper().startswith("NONE"):
            out[k] = ("none", None)
            continue
        cm = CALL_RE.search(body)
        if not cm:
            out[k] = ("unparsed", None)
            continue
        args = [a.strip() for a in cm.group(2).split(",")]
        c = canon(cm.group(1), args, rota)
        out[k] = ("ok", c) if c is not None else ("invalid", None)
    return out


def filter_allowed(det, rota):
    """A relation the note's section does not allow is treated as invalid."""
    out = {}
    for k, (st, v) in det.items():
        if st == "ok" and v[0] not in ALLOWED.get(route(rota.lines[k], rota), set()):
            out[k] = ("disallowed", None)
        else:
            out[k] = (st, v)
    return out


def parse_output(text, rota, wanted, routed=False):
    """{line: constraint | None} for lines that cast a vote (NONE or a valid constraint)."""
    det = parse_detailed(text, rota, wanted)
    if routed:
        det = filter_allowed(det, rota)
    return {k: v for k, (st, v) in det.items() if st in ("none", "ok")}


def extract(llm, budget, rota, line_ids, tag="extract", routed=True, bias=True, examples=True):
    msgs = build_messages(rota, line_ids, routed, bias, examples)
    text = llm.complete(budget, msgs, tag=tag)
    return parse_output(text, rota, set(line_ids), routed), text
