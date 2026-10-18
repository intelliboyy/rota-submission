"""DEVELOPMENT ONLY: reference labeller written from the visible phrasings.

It turns each visible line into a gold constraint so we can (a) prove the
solver reproduces visible_key.json and (b) measure the model's per-line
extraction accuracy.  It is template-bound, so it would fail on the held-out
phrasing -- which is exactly why the submitted system does not use it.
"""
import re

from eval.common import ROOT  # noqa: F401  (sets sys.path)
from rotasolve.schema import canon

HEDGES = ("i'm fairly sure ", "from what i recall, ", "as far as i know, ", "i believe ",
          "going off the roster, ", "if memory serves, ", "my recollection is that ",
          "unless i have this wrong, ", "speaking from memory, ", "i'm reasonably confident ")
STN = ["intake", "calibration", "packing"]


def strip_line(line):
    s = line.strip()
    head, sep, tail = s.partition(": ")
    if sep and len(head) < 60:
        s = tail
    low = s.lower()
    for h in HEDGES:
        if low.startswith(h):
            return s[len(h):]
    return s


def _table(N, S, T):
    P = f"({N})"
    t = []

    def add(rel, rx, order):
        t.append((rel, re.compile("^" + rx + r"\.$", re.I), order))
    add("AT", f"{P} is on the {T} block", "pt"); add("AT", f"the {T} block is {P}'s", "tp")
    add("AT", f"{P} takes {T}, as things stand", "pt"); add("AT", f"{P} is the one who opens up at {T}", "pt")
    add("AT", f"whoever drew the {T} block, it was {P}", "tp"); add("AT", f"{T} is when {P} is scheduled", "tp")
    add("NOT_AT", f"{P} is not on the {T} block", "pt"); add("NOT_AT", f"{T} is the one block {P} is definitely not on", "tp")
    add("NOT_AT", f"{P} is unavailable at {T}", "pt")
    add("NOT_AT", f"{P} has a standing commitment that rules out the {T} block entirely", "pt")
    add("NOT_AT", f"you will not find {P} on the {T} block", "pt"); add("NOT_AT", f"the {T} block is not {P}'s", "tp")
    add("BEFORE", f"{P} works earlier in the day than {P}", "ab"); add("BEFORE", f"{P} comes later in the day than {P}", "ba")
    add("BEFORE", f"{P}'s block falls somewhere earlier than {P}'s", "ab"); add("BEFORE", f"{P} is done before {P} starts", "ab")
    add("BEFORE", f"{P} takes over from {P} later in the day", "ba"); add("BEFORE", f"by the time {P} starts, {P} has already been on", "ba")
    add("IMM_BEFORE", f"{P} is on the block directly after {P}", "ba"); add("IMM_BEFORE", f"{P} is on the block immediately before {P}", "ab")
    add("IMM_BEFORE", f"{P} relieves {P} directly, with no block in between", "ba"); add("IMM_BEFORE", f"{P} then {P}, back to back", "ab")
    add("IMM_BEFORE", f"{P} hands straight over to {P}", "ab")
    add("IMM_BEFORE", f"there is no block between {P}'s and {P}'s, in that order", "ab")
    add("BETWEEN", f"{P} sits between {P} and {P} on the rota", "mab")
    add("BETWEEN", f"{P} is on after one of {P} and {P} and before the other", "mab")
    add("BETWEEN", f"{P}'s block falls between {P}'s and {P}'s, in one order or the other", "mab")
    add("BETWEEN", f"{P} works at some point between {P} and {P}, not necessarily adjacent to either", "mab")
    add("BETWEEN", f"whichever way round {P} and {P} are, {P} is between them", "abm")
    add("BETWEEN", f"put {P} between {P} and {P}, though not necessarily next to either", "mab")
    add("STATION", f"{S} is {P}'s station", "sp"); add("STATION", f"{P} is on {S}", "ps")
    add("STATION", f"{P} has {S} this week", "ps"); add("STATION", f"{S} is covered by {P}", "sp")
    add("STATION", f"{P} is assigned to {S}", "ps"); add("STATION", f"the {S} station is down to {P}", "sp")
    add("NOT_STATION", f"{P} is not on {S}", "ps"); add("NOT_STATION", f"{P} has not been put on {S}", "ps")
    add("NOT_STATION", f"{P} is not assigned to {S}", "ps"); add("NOT_STATION", f"{S} is covered by someone other than {P}", "sp")
    add("NOT_STATION", f"you can rule {P} out for {S}", "ps"); add("NOT_STATION", f"{S} is not {P}'s station", "sp")
    add("STATION_BEFORE", f"the {S} station is covered earlier in the day than {P}'s block", "sp")
    add("STATION_BEFORE", f"{P} is on later than whoever has {S}", "ps")
    add("STATION_BEFORE", f"the person on {S} precedes {P}", "sp")
    add("STATION_BEFORE", f"whoever is on {S} works earlier in the day than {P}", "sp")
    add("STATION_BEFORE", f"{S} is covered before {P} comes on", "sp")
    add("STATION_BEFORE", f"whoever has {S} is done before {P} starts", "sp")
    return t


def gold_line(line, rota):
    N = "|".join(sorted(rota.names, key=len, reverse=True))
    S = "(%s)" % "|".join(rota.stations)
    T = r"(\d\d:\d\d)"
    s = strip_line(line)
    for rel, rx, order in _table(N, S, T):
        m = rx.match(s)
        if not m:
            continue
        g = dict(zip(order, m.groups()))
        if rel in ("AT", "NOT_AT"):
            args = [g["p"], g["t"]]
        elif rel in ("BEFORE", "IMM_BEFORE"):
            args = [g["a"], g["b"]]
        elif rel == "BETWEEN":
            args = [g["m"], g["a"], g["b"]]
        elif rel in ("STATION", "NOT_STATION"):
            args = [g["p"], g["s"].lower()]
        else:  # STATION_BEFORE
            args = [g["s"].lower(), g["p"]]
        return canon(rel, args, rota)
    return None


def gold_constraints(rota):
    out = {}
    for i, l in enumerate(rota.lines):
        c = gold_line(l, rota)
        if c:
            out[i] = c
    return out
