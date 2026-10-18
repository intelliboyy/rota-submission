# Shift-Notes Rota Solver

**Take-home:** Architecture Under a Fixed, Weak Model  
**Author:** Anshuman Pathak  
**Python:** 3.12 (developed/tested with 3.12.10)  
**Answering model:** `ibm-granite/granite-4.2-8b`  
**Sampling:** `temperature=1.0`, `top_p=0.95`, reasoning disabled

This repository turns noisy shift notes into one of three structured outcomes: a unique rota, every valid rota when the notes are ambiguous, or verbatim citations that establish a contradiction. The model performs **constraint extraction only**; a deterministic solver decides the case and constructs the answer.

## Results on the visible set

The visible set contains 60 items, balanced across the three cases (20 each). These are the latest single-run scorer results recorded during development. Generation is sampled at temperature 1.0, so a later run can differ. These are **visible-set results, not held-out results**.

| Budget | Macro exact match | Unique exact match | Ambiguous exact match | Inconsistent exact match | Model calls per item | Budget violations |
|---|---:|---:|---:|---:|---:|---:|
| 1× | **36.67%** | 40% (8/20) | 20% (4/20) | 50% (10/20) | exactly 1 | 0 |
| 3× | **55.00%** | 55% (11/20) | 50% (10/20) | 60% (12/20) | exactly 3 | 0 |
| 10× | **76.67%** | 80% (16/20) | 60% (12/20) | 90% (18/20) | 7–10; mean 9.72 | 0 |

Exact match means the **case and its contents must both be right**. For an ambiguous item, that means every valid assignment; for an inconsistent item, it means a valid minimal conflict, not just the label. `macro_exact_match` is the mean of the three per-case exact-match rates. The 10× run gets the best visible-set result, while ambiguous items remain the weakest case at that budget.

### Case-label confusion

The matrices below are *case-label predictions only*. They do not score assignment or citation content. Rows are the true case, columns are the declared case; cells are item counts.

**1×**

| True \\ declared | Unique | Ambiguous | Inconsistent |
|---|---:|---:|---:|
| Unique | 8 | 10 | 2 |
| Ambiguous | 1 | 15 | 4 |
| Inconsistent | 1 | 4 | 15 |

**3×**

| True \\ declared | Unique | Ambiguous | Inconsistent |
|---|---:|---:|---:|
| Unique | 11 | 8 | 1 |
| Ambiguous | 1 | 17 | 2 |
| Inconsistent | 3 | 1 | 16 |

**10×**

| True \\ declared | Unique | Ambiguous | Inconsistent |
|---|---:|---:|---:|
| Unique | 17 | 3 | 0 |
| Ambiguous | 1 | 17 | 2 |
| Inconsistent | 1 | 0 | 19 |

A diagonal label is not necessarily an exact answer: for example, one of the 17 unique labels at 10× still has an incorrect assignment. The score must be read alongside the confusion matrix, not replaced by it.

## Architecture

### 1. Parse the rota, not the prose

`rotasolve.parse` reads the header to recover the exact person, time-block, station, and station-holder strings. These strings are the canonical vocabulary for the rest of the pipeline. The intended items have five people, five time blocks, three stations and three station-holders.

### 2. Route each note to a small label space

`rotasolve.route` uses header vocabulary and surface structure—not a hand-written matcher for the body text—to route a note into one section:

| Section | Routing signal | Allowed relations |
|---|---|---|
| `T` | Mentions a block time | `AT`, `NOT_AT` |
| `S` | Mentions a station | `STATION`, `NOT_STATION`, `STATION_BEFORE` |
| `P` | Names two people, no station or time | `BEFORE`, `IMM_BEFORE` |
| `M` | Names three people, no station or time | `BETWEEN` |
| `Z` | Anything else | `NONE` (not sent to the model) |

The relation vocabulary is deliberately small: `AT`, `NOT_AT`, `BEFORE`, `IMM_BEFORE`, `BETWEEN`, `STATION`, `NOT_STATION`, and `STATION_BEFORE`. The prompt spells out argument direction—for example, `BEFORE(first, second)` always puts the earlier person first—and treats hedges as full-strength statements. Refused wishes, hypotheticals, unconfirmed claims, past arrangements, and filler should be labeled `NONE`.

### 3. Extract with the fixed model and validate strictly

`rotasolve.prompt` provides relation definitions, one answer per line, short meaning-based examples, and per-section base-rate hints. It does not ask the model to solve the rota. The model is instructed to use the supplied relation syntax or `NONE` for each note.

`rotasolve.extract` parses the response and `rotasolve.schema.canon` rejects unknown names, blocks, stations, wrong arity, and invalid self-order relations. Values are canonicalized against the header strings. For routed prompts, a relation that is not allowed in that section is rejected. Every successful API request sends `X-Item-Id`; SDK retries are disabled so hidden retries cannot exceed the call budget.

### 4. Vote, solve exactly, repair selectively

Calls are repeated at higher budgets and their line-level constraints are combined with a budget-specific acceptance threshold. Remaining calls may re-read lines implicated in disagreement or an invalid solution. The threshold is below a simple majority at 3× and 10× because missed real constraints are more common than invented constraints in the extraction audit.

The symbolic solver enumerates all legal assignments for the intended header: 5! time permutations × 3! station-holder mappings = **720 candidates**. Each constraint becomes a bit mask over these candidates. Intersecting the masks gives the number of consistent assignments:

- zero assignments → `inconsistent`, with a minimal conflicting set of note lines;
- one assignment → `unique`, with a complete assignment for every person;
- two to four assignments → `ambiguous`, with every consistent assignment returned.

The solver is exact over the parsed constraints; end-to-end errors mainly come from the model failing to read a line correctly.

## What the extraction audit says

The routed one-pass extraction report is saved in [`eval/extraction_report_v3.md`](eval/extraction_report_v3.md), with line-level examples in [`eval/extraction_errors.md`](eval/extraction_errors.md). In that audit:

- **441/537 real-constraint lines were recovered correctly (82.1% recall).**
- **8/180 near-miss lines** were incorrectly treated as constraints; there were **0/420** false positives on pure filler.
- Only **13/60 items** had every line extracted correctly.
- `BETWEEN` was the most difficult relation (0.72 recall), followed by `IMM_BEFORE` (0.75) and `BEFORE` (0.78). Argument direction/order is a recurring failure mode.

Line recall does not translate directly into item exact match. One missed or reversed constraint can change a unique case into an ambiguous or inconsistent one, and several relation-direction errors are correlated across samples; voting does not reliably remove them.

## Ablations and reproducibility

The ablation harness is implemented in `eval/ablate.py`. The current [`eval/ablation.md`](eval/ablation.md) and [`eval/ablation.csv`](eval/ablation.csv) contain the latest uploaded, configured-endpoint results: one run for each configuration/budget and zero budget violations. These files use the non-mock output schema; mock-backend results from `--mock noisy` are machinery checks and must not be treated as model-performance evidence.

The visible-set results below report **macro exact match (unique / ambiguous / inconsistent exact-match rates)**. All numbers are percentages. The dataset contains 60 visible items, balanced across the three cases; each ablation cell has one run, so no meaningful run-to-run standard deviation is available.

| Row | Component | 1×: macro (U/A/I) | 3×: macro (U/A/I) | 10×: macro (U/A/I) |
|---|---|---:|---:|---:|
| A | Flat prompt, one pass | 35.0% (35.0/30.0/40.0) | 41.7% (40.0/40.0/45.0) | 38.3% (35.0/35.0/45.0) |
| B | Routed sections, one pass | 41.7% (35.0/35.0/55.0) | 40.0% (35.0/30.0/55.0) | 40.0% (35.0/35.0/50.0) |
| B2 | Routed, no base-rate hint | 35.0% (35.0/20.0/50.0) | 35.0% (45.0/10.0/50.0) | 40.0% (40.0/25.0/55.0) |
| B3 | Routed, no demonstrations | 26.7% (20.0/20.0/40.0) | 25.0% (30.0/20.0/25.0) | 11.7% (5.0/0.0/30.0) |
| C | Voting with budget plan | 43.3% (50.0/30.0/50.0) | 46.7% (45.0/40.0/55.0) | 65.0% (65.0/50.0/80.0) |
| C3 | Majority-only acceptance (0.5) | 40.0% (40.0/25.0/55.0) | 43.3% (40.0/40.0/50.0) | 55.0% (55.0/50.0/60.0) |
| D | Full solver-guided repair | 36.7% (45.0/25.0/40.0) | 48.3% (50.0/45.0/50.0) | **70.0% (60.0/60.0/90.0)** |

All 21 ablation runs report zero budget violations. The full per-run values are available in [`eval/ablation.csv`](eval/ablation.csv); interpretation and the reproducibility command are documented in [`eval/ablation.md`](eval/ablation.md).

### What the ablation suggests

- **Voting improves with budget:** row C reaches 65.0% at 10×, versus 38.3% for the flat prompt (A) and 40.0% for routed one-pass prompting (B).
- **Solver-guided repair helps most at higher budget in this run:** D scores 36.7% at 1×, 48.3% at 3×, and 70.0% at 10×. Compared with C, D is lower by 6.6 percentage points at 1×, higher by 1.6 points at 3×, and higher by 5.0 points at 10×.
- **Demonstrations matter:** removing demonstrations (B3) reduces the 10× result to 11.7%, compared with 40.0% for B.
- **Base-rate hints help at lower budgets in this run:** B exceeds B2 at 1× and 3×, while they tie at 40.0% at 10×.
- **Adaptive acceptance beats majority-only acceptance:** C exceeds C3 at every budget, with a 10-point difference at 10×.

These are single-run results on the visible set, so they are descriptive rather than statistically conclusive and do not establish held-out generalization. The primary benchmark table above comes from a separate sampled run: its 10× score (76.7%) differs from row D here (70.0%). At temperature 1.0 and one run per setting, this is run-to-run variability, not a paired comparison.

To reproduce the ablation with the configured endpoint and local task data, run:

```bash
python -m eval.ablate --rows A B B2 B3 C C3 D --runs 1
```

The harness runs all listed rows at the 1×, 3×, and 10× budgets and writes `eval/ablation.md` and `eval/ablation.csv`. It makes multiple endpoint calls; inspect the row/budget plan before increasing `--runs`. Use `--mock noisy` only to validate the report-writing and budget-check code, not for model-performance claims.

## What I tried, what I kept

Early alternatives included a flat eight-relation prompt, demonstrations copied too closely from visible wording, multi-view calls that split sections instead of repeating the same routed view, majority-only acceptance, and a minimal-edit relaxer that removes constraints until a verdict becomes legal.

The default keeps routing, meaning-based examples, section-specific base-rate hints, strict canonicalization, exact search, line-indexed citations, and repeats plus solver-guided repair at 10×. It avoids visible-phrasing demonstrations because they risk overfitting the visible phrasing pool. The relaxer remains optional (`--relax`) and is off by default: deleting constraints can turn a genuinely inconsistent note into a falsely unique assignment. The multi-view plan remains available to the ablation harness, but repeated routed views are the default because their behavior is easier to compare across budgets.

## Limits and next steps

The current router is intentionally cheap and template-aware. Notes that refer to people by pronoun, use unexpected header phrasing, or mention an unexpected number of names may route to `Z` and be lost. Argument-direction mistakes and subtle distinctions between a real constraint and a refused wish remain the main language-model risks. The exact search is small for the provided rota format; the parser, router, and assumptions would need redesign for arbitrary staffing schedules.

With a month, I would prioritize: (1) a phrasing-held-out and human-written evaluation, grouped by writer so near-duplicate wording cannot leak across splits; (2) a model-based ablation with multiple runs and explicit uncertainty intervals; (3) targeted, relation-specific repair for `BETWEEN` and temporal-direction errors; (4) confidence calibration and a better method for selecting the next line to re-read; and (5) an exact CP-SAT/SAT encoding with independently checked minimal conflict cores if the rota size grows.

Constraint extraction is **model-based**, not a symbolic pattern extractor. Symbolic logic is used only after extraction to validate, enumerate solutions, and find contradictions. For notes by different writers, the approach should transfer when a sentence clearly expresses one of the eight relations, but the current routing and prompt are likely brittle to pronouns, cross-line references, unusual names, implied negation, new clock formats, and unfamiliar paraphrases. A disjoint-phrasing evaluation is necessary before claiming robustness to different authors.

## Setup

### Requirements and private settings

Use Python 3.12 and the pinned dependencies in `requirements.txt`. Do not commit `.env`, API keys, local task data, generated answers, or a local virtual environment.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env   # Windows PowerShell
# cp .env.example .env   # macOS/Linux
```

Fill `.env` with the endpoint base URL and API key supplied for the task. Keep the model set to `ibm-granite/granite-4.2-8b`. The client uses `temperature=1.0`, `top_p=0.95`, `extra_body={"reasoning": {"enabled": False}}`, `X-Item-Id`, and `max_retries=0` on every call. Never commit `.env`.

Copy these task-provided files into `data/` locally; they are ignored by Git:

- `items.json`
- `visible_key.json`
- `score.py`
- `example_answers.json` (format reference)

### Required entrypoint

The repo-root `run` launcher accepts an input path, a budget and an output path, as required by the brief.

```bash
# Windows PowerShell
python run data/items.json --budget 1x --out answers.json
python data/score.py data/visible_key.json answers.json

python run data/items.json --budget 3x --out answers-3x.json
python data/score.py data/visible_key.json answers-3x.json

python run data/items.json --budget 10x --out answers-10x.json
python data/score.py data/visible_key.json answers-10x.json
```

On macOS/Linux, the equivalent entrypoint is `./run data/items.json --budget 1x --out answers.json`. The launcher prints per-item call counts and violations and exits non-zero if any item falls outside its budget. Every item must receive at least one call.

Optional diagnostic flags include `--workers N`, `--log calls.jsonl`, `--debug-out diagnostics.json`, `--limit K`, `--no-repair`, `--no-vote`, `--no-bias`, and `--flat`. `--relax` enables the experimental minimal-edit fallback and is not part of the default system.

### Tests and offline checks

```bash
python -m unittest -v
python -m eval.check_solver
python -m eval.extraction_report --bias on
```

`eval.check_solver` uses a local gold reader to check solver/renderer behavior; it is an offline plumbing check, not a model score. The extraction report and the real ablation/final-check commands call the configured model endpoint. The extraction audit is based on the visible set and should not be described as held-out performance.

## Repository layout

```text
run                 Required CLI launcher
rotasolve/          Parsing, routing, prompts, extraction, voting, solving, rendering
 eval/              Solver checks, extraction audit, final-check and ablation scripts
 tests/             Unit, end-to-end and HTTP contract tests
 data/README.md     Explains where local task-provided files belong
requirements.txt    Pinned Python dependencies
.env.example        Safe template for local endpoint configuration
```
