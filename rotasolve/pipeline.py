"""Per-item orchestration: extract -> (vote) -> solve -> (repair) -> render."""
import itertools
import re
from collections import Counter
from dataclasses import dataclass, field

from .extract import extract
from .llm import BudgetExceeded, ItemBudget
from .parse import parse_item
from .route import route
from .solve import Space, and_all, min_cores, popcount, shrink_core

BUDGETS = {"1x": 1, "3x": 3, "10x": 10}


ALL = "STPM"
# 3x: three routed passes -> a real per-line majority.  10x: those three plus the
# sections re-read on their own (P and M, the hardest, twice): five or six votes
# per line, leaving one call for repair.
ROUTED_PLANS = {"1x": [ALL], "3x": [ALL] * 3,
                "10x": [ALL] * 3 + ["S", "T", "P", "M", "P", "M"]}
# alternative for the ablation: different views instead of repeats
MULTIVIEW_PLANS = {"1x": [ALL], "3x": [ALL, "ST", "PM"],
                   "10x": [ALL, ALL, "S", "T", "P", "M", "P", "M"]}
FLAT_PLANS = {"1x": [ALL], "3x": [ALL] * 3, "10x": [ALL] * 5}


@dataclass
class Config:
    bias: bool = True                        # tell the model the measured base rate per section
    routed: bool = True                      # sectioned prompt with per-section label spaces
    plans: dict = field(default_factory=lambda: {k: list(v) for k, v in ROUTED_PLANS.items()})
    # share of the vote weight a constraint needs to be accepted. Real misses are common and
    # invented constraints are rare, so extra budgets accept on less than a majority.
    accept: dict = field(default_factory=lambda: {"1x": 0.5, "3x": 0.33, "10x": 0.4})
    focus_weight: float = 1.0                # vote weight of a call that sees only some sections
    examples: bool = True      # worked examples in the extraction prompt
    repair: bool = True        # spend leftover calls re-reading suspicious lines
    relax: bool = False        # experimental: minimal edit when verdict is impossible
    conf_core: bool = True     # cite the core the model agreed on most
    max_suspects: int = 8


def flat_config(**kw):
    kw.setdefault("plans", {k: list(v) for k, v in FLAT_PLANS.items()})
    return Config(routed=False, **kw)


@dataclass
class Decision:
    kind: str
    count: int
    sols: list
    cores: list
    core: frozenset
    legal: bool


# ---------------------------------------------------------------- decision
def choose_core(cores, conf, use_conf):
    def key(c):
        cs = [conf.get(i, 1.0) for i in c]
        if use_conf:
            return (-min(cs), -sum(cs) / len(cs), len(c), sorted(c))
        return (len(c), sorted(c))
    return min(cores, key=key)


def decide_masks(space, masks, conf, use_conf=True):
    m = and_all(space, masks)
    cnt = popcount(m)
    if cnt == 0:
        cores = min_cores(space, masks) or [shrink_core(space, masks)]
        core = choose_core(cores, conf, use_conf)
        return Decision("inconsistent", 0, [], cores, core, min(len(c) for c in cores) >= 3)
    kind = "unique" if cnt == 1 else "ambiguous"
    legal = cnt == 1 or 2 <= cnt <= 4
    return Decision(kind, cnt, space.indices(m), [], frozenset(), legal)


def consensus(votes, accept=0.5):
    """votes: {line: [(value, weight), ...]} -> consensus constraints and confidences.

    The most-voted real constraint for a line is accepted when it holds at least
    `accept` of that line's total vote weight; otherwise the line is NONE.
    """
    cons, conf = {}, {}
    for i, v in votes.items():
        if not v:
            continue
        w = Counter()
        for val, wt in v:
            w[val] += wt
        total = sum(w.values())
        real = {x: wt for x, wt in w.items() if x is not None}
        if real:
            best = max(real, key=lambda x: (real[x], -[val for val, _ in v].index(x)))
            if real[best] / total >= accept - 1e-9:
                cons[i] = best
                conf[i] = real[best] / total
                continue
        conf[i] = w.get(None, 0.0) / total if w.get(None) else 1.0 - max(real.values(), default=0) / total
    return cons, conf


def relax(space, masks, conf, use_conf, max_remove=2):
    """Smallest, least-trusted deletion that turns an impossible verdict legal."""
    ids = sorted(masks)
    for r in range(1, max_remove + 1):
        best = None
        for rem in itertools.combinations(ids, r):
            sub = {i: masks[i] for i in ids if i not in rem}
            d = decide_masks(space, sub, conf, use_conf)
            if d.legal:
                cost = sum(conf.get(i, 1.0) for i in rem)
                if best is None or cost < best[0]:
                    best = (cost, rem, d)
        if best:
            return best[1], best[2]
    return (), None


# ---------------------------------------------------------------- suspects
def mentions(line, rota):
    low = line.lower()
    return (any(n.lower() in low for n in rota.names)
            and (re.search(r"\d\d:\d\d", line) or any(s in low for s in rota.stations)))


def pick_suspects(rota, votes, cons, dec, limit):
    disagree = [i for i, v in votes.items() if len({val for val, _ in v}) > 1]
    sus = []
    if dec.kind == "inconsistent":
        small = [c for c in dec.cores if len(c) < 3]
        sus += sorted(set().union(*small)) if small else sorted(dec.core)
    elif not dec.legal:
        sus += [i for i in votes if i not in cons and mentions(rota.lines[i], rota)]
    sus += disagree
    if dec.kind == "ambiguous":
        # ambiguity can mean a statement was skipped: re-read stubborn NONE lines,
        # in the sections where most notes are real statements first
        pri = {"M": 0, "P": 1, "S": 2, "T": 3}
        nones = [i for i in votes if i not in cons and route(rota.lines[i], rota) in pri]
        sus += sorted(nones, key=lambda i: (pri[route(rota.lines[i], rota)], i))
    seen, out = set(), []
    for i in sus:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out[:limit]


# ---------------------------------------------------------------- rendering
def render(rota, space, dec):
    if dec.kind == "inconsistent":
        return {"case": "inconsistent", "conflicts": [rota.lines[i] for i in sorted(dec.core)]}
    if dec.kind == "unique":
        return {"case": "unique", "assignment": space.assignment(dec.sols[0])}
    return {"case": "ambiguous", "assignments": [space.assignment(i) for i in dec.sols[:4]]}


# ---------------------------------------------------------------- item
def solve_item(item, budget_name, llm, cfg=None):
    cfg = cfg or Config()
    cap = BUDGETS[budget_name]
    bud = ItemBudget(item["id"], cap)
    rota = parse_item(item)
    space = Space(rota)
    n_lines = len(rota.lines)
    groups = [route(l, rota) for l in rota.lines]
    votes = {i: [] for i in range(n_lines)}

    def collect(ids, tag, weight):
        if not ids:
            return False
        res, _ = extract(llm, bud, rota, ids, tag, routed=cfg.routed, bias=cfg.bias, examples=cfg.examples)
        for i in ids:
            if i in res:
                votes[i].append((res[i], weight))
        return True

    def state():
        cons, conf = consensus(votes, cfg.accept[budget_name])
        masks = {i: space.mask(c) for i, c in cons.items()}
        return cons, conf, masks, decide_masks(space, masks, conf, cfg.conf_core)

    try:
        done = 0
        for spec in cfg.plans[budget_name][:cap]:
            ids = [i for i, g in enumerate(groups) if g in spec]
            focused = cfg.routed and set(spec) != set(ALL)
            if collect(ids, "extract", cfg.focus_weight if focused else 1.0):
                done += 1
        if done == 0:                                   # every item gets at least one call
            collect(list(range(n_lines)), "extract", 1.0)
        cons, conf, masks, dec = state()
        if cfg.repair:
            prev = None
            while bud.left > 0:
                sus = [i for i in pick_suspects(rota, votes, cons, dec, cfg.max_suspects) if groups[i] != "Z"]
                sig = (dec.kind, dec.count, dec.core)
                if not sus or (sig == prev and dec.legal):
                    break
                prev = sig
                collect(sus, "repair", cfg.focus_weight)
                cons, conf, masks, dec = state()
    except BudgetExceeded:
        cons, conf, masks, dec = state()

    removed = ()
    if cfg.relax and not dec.legal:
        removed, d2 = relax(space, masks, conf, cfg.conf_core)
        if d2:
            dec = d2

    info = {"kind": dec.kind, "count": dec.count, "legal": dec.legal, "calls": bud.used,
            "n_constraints": len(cons), "relaxed": list(removed),
            "core": sorted(dec.core)}
    return render(rota, space, dec), info
