"""The extraction prompt.  The model only LABELS lines; it never solves anything.

Examples deliberately use wording different from the visible notes so the
prompt is not tuned to one phrasing pool.
"""

SYSTEM = ("You convert lines of shift notes into formal constraints. "
          "You never solve the schedule. You output only the labels requested.")

RELATIONS = """RELATIONS (use exactly these names):
AT(person, block)          the line says the person works that block.
NOT_AT(person, block)      the line says the person is NOT on that block / is unavailable then.
BEFORE(first, second)      first's block is earlier in the day than second's (not necessarily next to it).
                           The FIRST argument is always the earlier person. "X is later than Y" -> BEFORE(Y, X).
IMM_BEFORE(first, second)  second works the very next block after first, with no block in between.
                           The FIRST argument is always the earlier person. "X takes over from Y right away" -> IMM_BEFORE(Y, X).
BETWEEN(middle, end1, end2) middle's block lies strictly between the blocks of end1 and end2, in either order.
STATION(person, station)   the person is on that station.
NOT_STATION(person, station) the person is NOT on that station. "Packing is covered by someone other than X" -> NOT_STATION(X, packing).
STATION_BEFORE(station, person) whoever works that station has an earlier block than the person.
NONE                       the line states none of the above."""

RULES = """RULES
- A hedge ("I believe", "as far as I know", "speaking from memory", "going off the roster") does NOT weaken a statement. Label the statement as if the hedge were absent.
- A prefix such as "It bears repeating:" or "Repeating myself:" only restates a line. Label what follows it.
- Use NONE for: filler; lists of who attended something; wishes or requests that were refused or unfulfilled; hypotheticals and counterfactuals ("would have been", "had it gone the other way"); things nobody could confirm or that were left open; and anything about a past period or an old arrangement.
- Use names exactly as written in the rota, blocks as HH:MM, stations in lower case.
- Every note gets exactly one answer line, including notes you label NONE. Never skip or merge notes and never write ranges such as L3-L5.
- Output exactly one line per note, in the form  L<number>: RELATION(args)  or  L<number>: NONE . No other text."""

EXAMPLE = """EXAMPLE (a different rota: Dana, Eli, Kai, Lena, Omar; blocks 07:00 09:00 11:00 13:00 15:00; stations intake, calibration, packing)
L1: Dana has the 09:00 slot.
L2: Honestly, I believe Omar cannot do 07:00.
L3: Eli finishes before Kai begins.
L4: Kai is later in the day than Dana.
L5: Lena's block comes ahead of Omar's.
L6: Lena comes straight after Kai, no gap.
L7: Omar takes over from Eli right away.
L8: Omar sits somewhere in the middle of Dana and Eli, order unknown.
L9: Dana and Kai bracket Lena, though not necessarily tightly.
L10: As far as I know, Eli lands after one of Lena and Kai and ahead of the other.
L11: Intake belongs to Kai.
L12: Lena has been given packing.
L13: As far as I recall, packing is not Dana's.
L14: Eli was never going to be on calibration, so cross him off.
L15: Whoever runs calibration starts earlier than Omar.
L16: Omar cannot begin until the intake operator has finished.
L17: The packing operator is ahead of Lena in the day.
L18: Eli asked for 13:00 but was refused.
L19: Had Kai been on 07:00 things would have been easier.
L20: Nobody remembers who took packing.
L21: Last spring Lena worked intake.
L22: If Dana moved to 11:00, Eli could take 09:00.
L23: Dana and Omar are car-sharing this month.
L24: Repeating myself: Lena follows Kai immediately.
ANSWER
L1: AT(Dana, 09:00)
L2: NOT_AT(Omar, 07:00)
L3: BEFORE(Eli, Kai)
L4: BEFORE(Dana, Kai)
L5: BEFORE(Lena, Omar)
L6: IMM_BEFORE(Kai, Lena)
L7: IMM_BEFORE(Eli, Omar)
L8: BETWEEN(Omar, Dana, Eli)
L9: BETWEEN(Lena, Dana, Kai)
L10: BETWEEN(Eli, Lena, Kai)
L11: STATION(Kai, intake)
L12: STATION(Lena, packing)
L13: NOT_STATION(Dana, packing)
L14: NOT_STATION(Eli, calibration)
L15: STATION_BEFORE(calibration, Omar)
L16: STATION_BEFORE(intake, Omar)
L17: STATION_BEFORE(packing, Lena)
L18: NONE
L19: NONE
L20: NONE
L21: NONE
L22: NONE
L23: NONE
L24: IMM_BEFORE(Kai, Lena)"""

MARK = "=== NOTES TO LABEL ==="


def build_messages_flat(rota, line_ids, examples=True):
    facts = (f"ROTA: {', '.join(rota.names)}\n"
             f"BLOCKS (earliest first): {', '.join(rota.blocks)}\n"
             f"STATIONS: {', '.join(rota.stations)}\n"
             f"PEOPLE ON A STATION: {', '.join(rota.holders)}")
    notes = "\n".join(f"L{i + 1}: {rota.lines[i]}" for i in line_ids)
    n = len(line_ids)
    demo = (EXAMPLE + "\n\n") if examples else ""
    user = (f"{RELATIONS}\n\n{RULES}\n\n{demo}{facts}\n\n{MARK}\n{notes}\n\n"
            f"There are {n} notes above. Give exactly {n} answer lines.\n\nANSWER")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


# ----------------------------------------------------------------------------
# Routed prompt: notes are grouped by what they mention and how many people they
# name (see route.py); each group only allows the relations that can apply.
from .route import route  # noqa: E402

TITLE = {
    "T": "notes that mention a block time. Allowed answers: AT, NOT_AT, NONE.",
    "S": "notes that mention a station. Allowed answers: STATION, NOT_STATION, STATION_BEFORE, NONE.",
    "P": "notes about two people, with no station or block time. Allowed answers: BEFORE, IMM_BEFORE, NONE. Most of them say who works earlier, later, or right after someone. Answer NONE only if the note says nothing about the order of their blocks (chat, favours, past events).",
    "M": "notes that name three people, with no station or block time. Allowed answers: BETWEEN, NONE. A note is BETWEEN when it places one person among the other two (between, in the middle of, flanked or bracketed by, after one and before the other). Answer NONE only for notes that merely list people doing something together.",
}

DEFS = {
    "T": """AT(person, block)       the note says the person works that block.
NOT_AT(person, block)   the note says the person is NOT on that block, or is unavailable then.
NONE                    anything else (wishes, refusals, hypotheticals, things nobody is sure of).""",
    "S": """STATION(person, station)       the person is on that station.
NOT_STATION(person, station)   the person is NOT on that station. "Packing is covered by someone other than X" -> NOT_STATION(X, packing).
STATION_BEFORE(station, person) whoever works that station has an earlier block than the person.
NONE                            anything else (past arrangements, wishes, things nobody is sure of).""",
    "P": """BEFORE(first, second)       first's block is earlier in the day than second's (not necessarily next to it).
                            The FIRST argument is always the earlier person. "X is later than Y" -> BEFORE(Y, X).
IMM_BEFORE(first, second)   second works the very next block after first, no block in between.
                            The FIRST argument is always the earlier person. "X takes over from Y right away" -> IMM_BEFORE(Y, X).
NONE                        the note says nothing about the order of the two people's blocks.""",
    "M": """BETWEEN(middle, end1, end2) middle's block lies strictly between the blocks of end1 and end2, in either order.
                             The middle person comes first; the two ends can be given in any order.
NONE                         the note only lists people, or says nothing about one being between the others.""",
}

EX = {
    "T": [("Dana has the 09:00 slot.", "AT(Dana, 09:00)"),
          ("Honestly, I believe Omar cannot do 07:00.", "NOT_AT(Omar, 07:00)"),
          ("15:00 belongs to Eli.", "AT(Eli, 15:00)"),
          ("Kai is off the 11:00 block.", "NOT_AT(Kai, 11:00)"),
          ("Eli asked for 13:00 but was refused.", "NONE"),
          ("Had Kai been on 07:00 things would have been easier.", "NONE"),
          ("If Dana moved to 11:00, Eli could take 09:00.", "NONE"),
          ("Nobody is sure whether Lena was down for 13:00.", "NONE")],
    "S": [("Intake belongs to Kai.", "STATION(Kai, intake)"),
          ("Lena has been given packing.", "STATION(Lena, packing)"),
          ("As far as I recall, packing is not Dana's.", "NOT_STATION(Dana, packing)"),
          ("Eli was never going to be on calibration, so cross him off.", "NOT_STATION(Eli, calibration)"),
          ("Whoever runs calibration starts earlier than Omar.", "STATION_BEFORE(calibration, Omar)"),
          ("Omar cannot begin until the intake operator has finished.", "STATION_BEFORE(intake, Omar)"),
          ("The packing operator is ahead of Lena in the day.", "STATION_BEFORE(packing, Lena)"),
          ("Repeating myself: Kai runs intake.", "STATION(Kai, intake)"),
          ("Nobody remembers who took packing.", "NONE"),
          ("Last spring Lena worked intake.", "NONE"),
          ("Dana would rather have calibration, but that was never agreed.", "NONE")],
    "P": [("Eli finishes before Kai begins.", "BEFORE(Eli, Kai)"),
          ("Kai is later in the day than Dana.", "BEFORE(Dana, Kai)"),
          ("Lena's block comes ahead of Omar's.", "BEFORE(Lena, Omar)"),
          ("I believe Omar works some time after Dana.", "BEFORE(Dana, Omar)"),
          ("Lena comes straight after Kai, no gap.", "IMM_BEFORE(Kai, Lena)"),
          ("Omar takes over from Eli right away.", "IMM_BEFORE(Eli, Omar)"),
          ("Dana is immediately followed by Kai.", "IMM_BEFORE(Dana, Kai)"),
          ("Repeating myself: Lena follows Kai immediately.", "IMM_BEFORE(Kai, Lena)"),
          ("Dana and Omar are car-sharing this month.", "NONE"),
          ("Kai lent Eli a charger on Monday.", "NONE"),
          ("Omar and Lena swapped shifts last winter.", "NONE")],
    "M": [("Omar sits somewhere in the middle of Dana and Eli, order unknown.", "BETWEEN(Omar, Dana, Eli)"),
          ("Dana and Kai bracket Lena, though not necessarily tightly.", "BETWEEN(Lena, Dana, Kai)"),
          ("As far as I know, Eli lands after one of Lena and Kai and ahead of the other.", "BETWEEN(Eli, Lena, Kai)"),
          ("Kai is flanked on either side, at some distance, by Omar and Dana.", "BETWEEN(Kai, Omar, Dana)"),
          ("Whichever of Dana and Kai goes first, Lena is somewhere in the gap.", "BETWEEN(Lena, Dana, Kai)"),
          ("Repeating myself: Omar falls between Lena and Eli.", "BETWEEN(Omar, Lena, Eli)"),
          ("Kai, Lena and Eli walked the site together on Tuesday.", "NONE"),
          ("Dana asked Omar and Eli to help with the audit.", "NONE")],
}


PRIOR = {
    "T": "About 40% of the notes in this section are real statements; the rest are wishes, refusals or hypotheticals.",
    "S": "About 80% of the notes in this section are real statements. Label a note unless it clearly fits a NONE case.",
    "P": "About 60% of the notes in this section are real statements about order. Label a note unless it clearly fits a NONE case.",
    "M": "About 85% of the notes in this section are real BETWEEN statements. Label a note unless it is clearly just a list of people doing something together.",
}


def build_messages(rota, line_ids, routed=True, bias=True, examples=True):
    if not routed:
        return build_messages_flat(rota, line_ids, examples=examples)
    groups = {"T": [], "S": [], "P": [], "M": []}
    for i in line_ids:
        g = route(rota.lines[i], rota)
        if g in groups:
            groups[g].append(i)
    facts = (f"ROTA: {', '.join(rota.names)}\n"
             f"BLOCKS (earliest first): {', '.join(rota.blocks)}\n"
             f"STATIONS: {', '.join(rota.stations)}\n"
             f"PEOPLE ON A STATION: {', '.join(rota.holders)}")
    secs = []
    for g in ("T", "S", "P", "M"):
        if not groups[g]:
            continue
        ex = "\n".join(f"Note: {n}\nAnswer: {a}" for n, a in EX[g])
        notes = "\n".join(f"L{i + 1}: {rota.lines[i]}" for i in groups[g])
        prior = (PRIOR[g] + "\n") if bias else ""
        demo = (f"\n\nWorked examples (a different rota: Dana, Eli, Kai, Lena, Omar):\n{ex}" if examples else "")
        secs.append(f"### SECTION {g}: {TITLE[g]}\n{prior}{DEFS[g]}{demo}\n\n{MARK}\n{notes}")
    n = sum(len(v) for v in groups.values())
    user = (f"{RULES}\n\n{facts}\n\nThe notes come in sections. Inside a section use only that section's allowed answers.\n\n"
            + "\n\n".join(secs)
            + f"\n\nThere are {n} notes in total. Give exactly {n} answer lines, one per note.\n\nANSWER")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
