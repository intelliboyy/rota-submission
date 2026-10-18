"""Exact reasoning: enumerate every consistent assignment, count, find cores.

Candidates = block placements x station placements (4,320 for 5 people / 3
stations).  Each constraint becomes a bitmask over the candidates, so a set of
constraints is satisfiable iff the AND of its masks is non-zero.
"""
import itertools


def popcount(x):
    return bin(x).count("1")


class Space:
    def __init__(self, rota):
        self.rota = rota
        self.pidx = {n: i for i, n in enumerate(rota.names)}
        self.bidx = {b: i for i, b in enumerate(rota.blocks)}
        self.sidx = {s: i for i, s in enumerate(rota.stations)}
        n, nb, ns = len(rota.names), len(rota.blocks), len(rota.stations)
        hidx = [self.pidx[h] for h in rota.holders]
        cands = []
        for bp in itertools.permutations(range(nb), n):          # block index per person
            for sp in itertools.permutations(range(ns), len(hidx)):
                st = [-1] * n
                ho = [None] * ns
                for h, s in zip(hidx, sp):
                    st[h] = s
                    ho[s] = h
                cands.append((bp, tuple(st), tuple(ho)))
        self.cands = cands
        self.N = len(cands)
        self.full = (1 << self.N) - 1
        self._mask = {}

    def holds(self, c, cand):
        rel = c[0]
        bp, st, ho = cand
        P = self.pidx
        if rel == "AT":
            return bp[P[c[1]]] == self.bidx[c[2]]
        if rel == "NOT_AT":
            return bp[P[c[1]]] != self.bidx[c[2]]
        if rel == "BEFORE":
            return bp[P[c[1]]] < bp[P[c[2]]]
        if rel == "IMM_BEFORE":
            return bp[P[c[2]]] == bp[P[c[1]]] + 1
        if rel == "BETWEEN":
            a, b, m = bp[P[c[2]]], bp[P[c[3]]], bp[P[c[1]]]
            return min(a, b) < m < max(a, b)
        if rel == "STATION":
            return st[P[c[1]]] == self.sidx[c[2]]
        if rel == "NOT_STATION":
            return st[P[c[1]]] != self.sidx[c[2]]
        if rel == "STATION_BEFORE":
            h = ho[self.sidx[c[1]]]
            return h is not None and bp[h] < bp[P[c[2]]]
        raise ValueError(rel)

    def mask(self, c):
        if c not in self._mask:
            bits = ["1" if self.holds(c, cd) else "0" for cd in self.cands]
            self._mask[c] = int("".join(reversed(bits)), 2)
        return self._mask[c]

    def indices(self, m, limit=8):
        out = []
        while m and len(out) < limit:
            low = m & -m
            out.append(low.bit_length() - 1)
            m ^= low
        return out

    def assignment(self, idx):
        bp, st, _ = self.cands[idx]
        out = {}
        for i, name in enumerate(self.rota.names):
            d = {"block": self.rota.blocks[bp[i]]}
            if st[i] >= 0:
                d["station"] = self.rota.stations[st[i]]
            out[name] = d
        return out


def and_all(space, masks):
    m = space.full
    for v in masks.values():
        m &= v
    return m


def min_cores(space, masks, max_size=6, max_tried=300000):
    """All minimal unsatisfiable subsets (as frozensets of line ids), size <= max_size."""
    ids = sorted(masks)
    if and_all(space, masks):
        return []
    found, tried = [], 0
    for r in range(1, min(len(ids), max_size) + 1):
        for sub in itertools.combinations(ids, r):
            tried += 1
            if tried > max_tried:
                return found
            s = set(sub)
            if any(f <= s for f in found):
                continue
            m = space.full
            for i in sub:
                m &= masks[i]
            if m == 0:
                found.append(frozenset(sub))
    return found


def shrink_core(space, masks):
    """Deletion-based fallback: one minimal core of an unsatisfiable set."""
    keep = sorted(masks)
    for i in list(keep):
        trial = [j for j in keep if j != i]
        m = space.full
        for j in trial:
            m &= masks[j]
        if m == 0:
            keep = trial
    return frozenset(keep)
