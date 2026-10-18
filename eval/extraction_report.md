| relation | correct | missed (said NONE/no vote) | wrong args or direction | recall |
|---|---|---|---|---|
| AT | 36 | 5 | 1 | 0.86 |
| BEFORE | 26 | 13 | 2 | 0.63 |
| BETWEEN | 90 | 52 | 6 | 0.61 |
| IMM_BEFORE | 42 | 10 | 3 | 0.76 |
| NOT_AT | 36 | 11 | 3 | 0.72 |
| NOT_STATION | 60 | 6 | 2 | 0.88 |
| STATION | 36 | 1 | 3 | 0.90 |
| STATION_BEFORE | 74 | 10 | 9 | 0.80 |

- overall line recall on real constraints: 400/537 = 0.745
- what happened to the 537 real-constraint lines: {'ok': 429, 'none': 88, 'missing': 5, 'disallowed': 9, 'invalid': 6}
- all lines by outcome: {'none': 341, 'skipped': 332, 'ok': 438, 'missing': 11, 'disallowed': 9, 'invalid': 6}  (invalid = relation/names rejected by validation; unparsed = no relation(...) found; disallowed = relation not allowed in that note's section; missing = line not answered; skipped = routed to Z, never sent, counts as NONE)
- false positives on near-miss lines: 9/180; on pure filler: 0/420
- items with every line right: 5/60
