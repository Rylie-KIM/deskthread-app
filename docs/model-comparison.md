# Model comparison report

[Back to the README](../README.md) · [Test report](test-report.md) · [Status](status.md)

Run on **23 November 2026**, MacBook Air M4, 24 GB, macOS 26.6.2. Tool: `eval/compare.py` (new). Data: the 65-file invented demo laptop (70 readable items), the eight tuning questions of `eval/`, the same prompts and pipeline for every model, **3 runs per model**, story clock 22 Nov 2026 19:00.

**No model was downloaded for this report.** Only the three answering models already on this Mac were compared. The other five models of the AI model page (Llama 3.1 8B, Llama 3.2 3B, gpt-oss 20B, Nemotron Mini, SmolLM2) were **not run**; they would need a download of about 25 GB.

## Result

| | No model (baseline) | **Gemma 4** `gemma4:e4b` | Gemma 4 small `gemma4:e2b` | Phi-4 mini |
|---|---|---|---|---|
| Passed, run 1 / 2 / 3 | 2 of 8 | **5 / 5 / 6** of 8 | 3 / 3 / 3 of 8 | 2 / 2 / 2 of 8 |
| Median seconds per question | none | **9.5** | 15.7 | 19.0 |
| Slowest question | none | 25 s | 34 s | **317 s** (two questions ran into the 300 s limit) |
| Same cited notes in all 3 runs | none | 6 of 8 questions | 6 of 8 | 8 of 8 |
| Download size (as listed in the app) | none | 6.6 GB | 4.6 GB | 2.5 GB |
| Digest pinned in DeskThread | none | yes (default) | yes | yes |

The baseline is an ordinary exact-phrase search of the question with no model. It passes only the two "not found" questions, because it finds nothing, and none of the questions that need an answer. That is the reason for using a model at all.

## Per question (P = pass, F = fail, one letter per run)

| Question | Baseline | Gemma 4 | Gemma 4 small | Phi-4 mini |
|---|---|---|---|---|
| Q01 What did I promise Sam? | F | FFF | FFF | FFF |
| Q02 What salary did I promise Sam? (must be "not found") | P | PPP | PPP | PPP |
| Q03 Is the February conference still happening? | F | PPP | FFF | FFF |
| Q04 What is still open with Sam? | F | PPP | FFF | FFF |
| Q05 Did HR approve the money for Sam's course? | F | PPP | FFF | FFF (timeout) |
| Q06 Alex's performance (must be "not found") | P | PPP | PPP | FFF |
| Q07 Ideas for the offsite? | F | FFP | FFF | FFF (timeout) |
| Q08 What did I promise Alex? | F | FFF | PPP | PPP |

## What this shows

- **Gemma 4 is the best of the three on this data**, and the fastest. It is the default for that reason, and this run supports it.
- **Gemma 4 small and Phi-4 mini lose the questions that need joining several notes** (Q03, Q04, Q05). Gemma 4 small keeps the "not found" behaviour. Phi-4 mini does not on Q06.
- **Phi-4 mini is unreliable in time:** two questions reached the 300 s limit in every run.
- **No model passes Q01 (What did I promise Sam?).** The course point is reported as open where the ground truth says done. This is the same failure as in the [test report](test-report.md).
- **Q08 is the reverse:** Gemma 4 fails it and the two smaller models pass it. A bigger model is not better on every question.
- **Results are not fully stable.** Gemma 4 gave 5, 5 and 6 and changed its cited notes between runs on Q05 and Q07. In the earlier evaluation of the same day, the same model on the same data passed Q06 and Q07 and failed Q04 and Q08 (5 of 8 as well, but not the same five). Read the totals as "about 5 of 8", not as exact.

## Limits of this comparison

- Eight questions and three runs: small samples. One question is 12.5 percentage points.
- Only three models, all from the Gemma and Phi families. **There is no Llama comparison**, although the plan named Llama as a reference model. It needs the download.
- Prompts were tuned with Gemma 4 only (the tuning set was used for that), so the other models are at a disadvantage by construction.
- Temperature and seed were the application's own settings; they were not fixed for this report.
- Picture reading by the models was not compared: macOS text recognition reads the pictures in all runs.
- The held-out question set was not used.

## Re-run

```bash
make demo-data-core   # or: uv run python demo-data/make_demo_data.py --core --out <folder>
DESKTHREAD_NOW=2026-11-22T19:00:00+00:00 uv run python -m eval.compare \
  --models gemma4:e4b,gemma4:e2b,phi4-mini:latest --runs 3 --folder <folder> --out result.json
```

It refuses a model that is not on the Mac and never downloads one.
