| relation | correct | missed (said NONE/no vote) | wrong args or direction | recall |
|---|---|---|---|---|
| AT | 40 | 1 | 1 | 0.95 |
| BEFORE | 32 | 6 | 3 | 0.78 |
| BETWEEN | 106 | 35 | 7 | 0.72 |
| IMM_BEFORE | 41 | 10 | 4 | 0.75 |
| NOT_AT | 43 | 6 | 1 | 0.86 |
| NOT_STATION | 63 | 3 | 2 | 0.93 |
| STATION | 37 | 1 | 2 | 0.93 |
| STATION_BEFORE | 79 | 9 | 5 | 0.85 |

- overall line recall on real constraints: 441/537 = 0.821
- what happened to the 537 real-constraint lines: {'ok': 466, 'none': 64, 'missing': 3, 'invalid': 2, 'disallowed': 2}
- all lines by outcome: {'none': 329, 'missing': 329, 'ok': 474, 'unparsed': 1, 'invalid': 2, 'disallowed': 2}  (invalid = relation/names rejected by validation; unparsed = no relation(...) found; disallowed = relation not allowed in that note's section; missing = line not answered)
- false positives on near-miss lines: 8/180; on pure filler: 0/420
- items with every line right: 13/60
