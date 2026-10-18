# Visible-set results — one run per budget

These values are the latest explicit scorer outputs recorded during development. Each budget was run once on the 60-item visible set (20 items per true case). Sampling is stochastic at temperature 1.0, so this is a result snapshot, not an estimate across repeated runs or a held-out score.

| budget | macro exact match | unique exact match | ambiguous exact match | inconsistent exact match | calls per item | budget violations |
|---|---:|---:|---:|---:|---|---:|
| 1x | 36.67% | 40.0% (8/20) | 20.0% (4/20) | 50.0% (10/20) | exactly 1 | 0 |
| 3x | 55.00% | 55.0% (11/20) | 50.0% (10/20) | 60.0% (12/20) | exactly 3 | 0 |
| 10x | 76.67% | 80.0% (16/20) | 60.0% (12/20) | 90.0% (18/20) | 7–10 (mean 9.72) | 0 |

## Case-label confusion matrices

Rows are true labels; columns are declared labels. These count only the predicted case and do not verify assignment or citation content.

### 1x

| true \\ declared | unique | ambiguous | inconsistent |
|---|---:|---:|---:|
| unique | 8 | 10 | 2 |
| ambiguous | 1 | 15 | 4 |
| inconsistent | 1 | 4 | 15 |

### 3x

| true \\ declared | unique | ambiguous | inconsistent |
|---|---:|---:|---:|
| unique | 11 | 8 | 1 |
| ambiguous | 1 | 17 | 2 |
| inconsistent | 3 | 1 | 16 |

### 10x

| true \\ declared | unique | ambiguous | inconsistent |
|---|---:|---:|---:|
| unique | 17 | 3 | 0 |
| ambiguous | 1 | 17 | 2 |
| inconsistent | 1 | 0 | 19 |

Exact-match rates and confusion counts differ because a correctly classified case can still have the wrong assignment or conflict citations.
