"""Retrieval step: decide which label space (if any) a note can belong to.

Uses only header vocabulary (person names, station names, HH:MM block times)
and counts, never the wording of a note.  On the 60 visible items this separates
the relation families perfectly (tests/test_all.py checks it):

  S  mentions a station (and a person)       STATION, NOT_STATION, STATION_BEFORE
  T  mentions an HH:MM block (and a person)  AT, NOT_AT
  P  names exactly two people, no station/time   BEFORE, IMM_BEFORE
  M  names exactly three people, no station/time BETWEEN
  Z  anything else: cannot state a relation, never sent to the model (answer NONE)

Known limit: a statement that refers to people by pronoun, or names fewer or
more people than the relation needs, would be routed to Z and lost.
"""
import re

TIME = re.compile(r"\d{1,2}:\d{2}")

ALLOWED = {
    "S": {"STATION", "NOT_STATION", "STATION_BEFORE"},
    "T": {"AT", "NOT_AT"},
    "P": {"BEFORE", "IMM_BEFORE"},
    "M": {"BETWEEN"},
    "Z": set(),
}


def n_names(line, rota):
    return sum(1 for n in rota.names if re.search(r"\b" + re.escape(n) + r"\b", line, re.I))


def route(line, rota):
    k = n_names(line, rota)
    if k == 0:
        return "Z"
    low = line.lower()
    if any(s.lower() in low for s in rota.stations):
        return "S"
    if TIME.search(line):
        return "T"
    return {2: "P", 3: "M"}.get(k, "Z")
