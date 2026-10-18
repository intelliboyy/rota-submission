"""Fake model backends for offline testing (same interface as OpenAIBackend)."""
import random
import re
import threading

from eval.common import ROOT  # noqa: F401
from eval.gold import gold_constraints
from rotasolve.parse import parse_item
from rotasolve.prompt import MARK
from rotasolve.schema import fmt


def _asked_lines(messages):
    user = messages[-1]["content"].split(MARK, 1)[-1]
    return [int(m.group(1)) for m in re.finditer(r"^L(\d+): ", user, re.M)]


class GoldBackend:
    """Answers with the reference labels: a perfect reader."""

    def __init__(self, items):
        self.by_id = {it["id"]: it for it in items}
        self._cache = {}

    def gold(self, item_id):
        if item_id not in self._cache:
            rota = parse_item(self.by_id[item_id])
            self._cache[item_id] = (rota, gold_constraints(rota))
        return self._cache[item_id]

    def labels(self, item_id, messages):
        rota, gold = self.gold(item_id)
        return rota, {k: gold.get(k - 1) for k in _asked_lines(messages)}

    def __call__(self, item_id, messages):
        _, lab = self.labels(item_id, messages)
        return "\n".join(f"L{k}: {fmt(c) if c else 'NONE'}" for k, c in lab.items())


class NoisyBackend(GoldBackend):
    """A reader that drops real constraints, flips order, or invents some."""

    def __init__(self, items, p_drop=0.05, p_flip=0.03, p_fp=0.05, seed=0):
        super().__init__(items)
        self.p = (p_drop, p_flip, p_fp)
        self.seed, self.n, self._lock = seed, {}, threading.Lock()

    def __call__(self, item_id, messages):
        with self._lock:
            self.n[item_id] = self.n.get(item_id, 0) + 1
            n = self.n[item_id]
        rng = random.Random(f"{self.seed}-{item_id}-{n}")
        rota, lab = self.labels(item_id, messages)
        out = []
        for k, c in lab.items():
            if c and rng.random() < self.p[0]:
                c = None
            elif c and c[0] in ("BEFORE", "IMM_BEFORE") and rng.random() < self.p[1]:
                c = (c[0], c[2], c[1])
            elif c is None and rng.random() < self.p[2] and re.search(r"\d\d:\d\d", rota.lines[k - 1]):
                c = ("NOT_AT", rng.choice(rota.names), rng.choice(rota.blocks))
            out.append(f"L{k}: {fmt(c) if c else 'NONE'}")
        return "\n".join(out)


class PerturbBackend(GoldBackend):
    """Deliberately wrong reader: used to prove answers depend on model output."""

    def __init__(self, items, drop_rel):
        super().__init__(items)
        self.drop_rel = drop_rel

    def __call__(self, item_id, messages):
        _, lab = self.labels(item_id, messages)
        return "\n".join(
            f"L{k}: {fmt(c) if c and c[0] != self.drop_rel else 'NONE'}" for k, c in lab.items())
