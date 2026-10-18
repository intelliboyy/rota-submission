# Ablation report status

**Important: the table below is from the mock reader and checks the evaluation machinery only. These are not Granite scores and must not be used as evidence of model performance.** A real, controlled Granite ablation has not been recorded in this snapshot.

| id | component | mock macro exact match | runs |
|---|---|---:|---:|
| A | Flat prompt, one pass | 81.7% ±0.0 | 1 |
| B | Routed sections, one pass | 81.7% ±0.0 | 1 |

The values are expected to reflect the mock backend's behavior, not the fixed model. Generate the model-based table with the configured task endpoint:

```bash
python -m eval.ablate --rows A B B2 B3 C C3 D --runs 1
```

The command tests all three budgets by default and overwrites `eval/ablation.md` and `eval/ablation.csv`. It makes many model calls; inspect the configuration before increasing `--runs`. Use `--mock noisy` only to validate the report-writing and budget-check code.
