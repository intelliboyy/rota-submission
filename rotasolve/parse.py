"""Deterministic parsing of an item: header facts + numbered body lines."""
import re
from dataclasses import dataclass, field

TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")


@dataclass
class Rota:
    item_id: str
    header: str
    names: list
    blocks: list      # in time order
    stations: list
    holders: list     # people who are on a station
    lines: list = field(default_factory=list)   # raw body lines, index = line id


def norm_time(s):
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", s or "")
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def _split_list(s):
    s = s.replace(" and ", ", ")
    return [x.strip() for x in s.split(",") if x.strip()]


def parse_item(item):
    text = item["text"]
    raw = text.split("\n")
    hi = next((i for i, l in enumerate(raw) if "rota:" in l), 0)
    header = raw[hi]
    body = [l.strip() for l in raw[hi + 1:] if l.strip()]

    m = re.search(r"rota:\s*([^.]*)\.", header)
    if not m:
        raise ValueError(f"{item.get('id')}: cannot read rota from header")
    names = _split_list(m.group(1))

    m = re.search(r"Blocks run\s+(.*?)(?:,?\s+one person per block|\.)", header)
    seg = m.group(1) if m else header
    blocks = [norm_time(f"{h}:{mm}") for h, mm in TIME.findall(seg)]
    if not blocks:
        raise ValueError(f"{item.get('id')}: cannot read blocks")

    m = re.search(r"one person on each:\s*([^.]*)\.", header)
    stations = _split_list(m.group(1)) if m else []

    m = re.search(r"on a station are\s*([^;.]*)", header)
    holders = _split_list(m.group(1)) if m else []
    holders = [h for h in holders if h in names]
    if not holders:
        holders = names[:len(stations)]
    return Rota(item.get("id", "?"), header, names, blocks, stations, holders, body)
