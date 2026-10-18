"""The constraint vocabulary the model must emit, and strict canonicalisation.

Every model output is forced through canon(): unknown names/blocks/stations,
wrong arity or nonsense (a person before themselves) are rejected, and all
surviving strings are the exact ones from the header.
"""
from .parse import norm_time

# relation -> argument kinds
SPEC = {
    "AT": ("name", "time"),               # person works block
    "NOT_AT": ("name", "time"),           # person does not work block
    "BEFORE": ("name", "name"),           # first has an earlier block than second
    "IMM_BEFORE": ("name", "name"),       # second has the very next block after first
    "BETWEEN": ("name", "name", "name"),  # middle strictly between the two others
    "STATION": ("name", "station"),       # person is on station
    "NOT_STATION": ("name", "station"),   # person is not on station
    "STATION_BEFORE": ("station", "name"),  # whoever is on station has earlier block than person
}


def canon(rel, args, rota):
    rel = (rel or "").upper()
    if rel not in SPEC or len(args) != len(SPEC[rel]):
        return None
    names = {n.lower(): n for n in rota.names}
    stations = {s.lower(): s for s in rota.stations}
    args = _reorder(SPEC[rel], list(args), names, stations)
    out = []
    for kind, a in zip(SPEC[rel], args):
        a = (a or "").strip().strip("'\"`")
        if a.lower().endswith("'s"):
            a = a[:-2]
        if kind == "name":
            v = names.get(a.lower())
        elif kind == "station":
            v = stations.get(a.lower())
        else:
            v = norm_time(a)
            v = v if v in rota.blocks else None
        if v is None:
            return None
        out.append(v)
    if rel in ("BEFORE", "IMM_BEFORE") and out[0] == out[1]:
        return None
    if rel == "BETWEEN":
        m, a, b = out
        if len({m, a, b}) < 3:
            return None
        a, b = sorted((a, b))      # endpoints are unordered: canonical form
        out = [m, a, b]
    return (rel, *out)


def _kind_of(a, names, stations):
    a = (a or "").strip().strip("'\"`")
    if a.lower().endswith("'s"):
        a = a[:-2]
    if a.lower() in names:
        return "name"
    if a.lower() in stations:
        return "station"
    return "time" if norm_time(a) else None


def _reorder(kinds, args, names, stations):
    """If the model got the argument ORDER wrong but each argument is clearly a
    name / station / time, put them in the order the relation expects.  Names,
    stations and times are disjoint, so this cannot invent anything."""
    types = [_kind_of(a, names, stations) for a in args]
    if None in types or list(types) == list(kinds) or sorted(types) != sorted(kinds):
        return args
    pool = list(zip(types, args))
    out = []
    for k in kinds:
        j = next(i for i, (t, _) in enumerate(pool) if t == k)
        out.append(pool.pop(j)[1])
    return out


def fmt(c):
    return f"{c[0]}({', '.join(c[1:])})"
