# Test report

[Back to the README](../README.md) · [Traceability (need → feature → test)](traceability.md) · [Status](status.md)

Run on **23 November 2026**, MacBook Air M4 (Mac16,12), 24 GB, macOS 26.6.2, the `main` branch of that day. Model: `gemma4:e4b` (pinned digest), run locally.

## Result in one line

**180 of 180 automated tests pass. The evaluation with the real model is weaker than before: 5 of 8 on the small demo laptop, 4 of 8 on the rich one.**

## 1. Automated checks (`make check`, no model)

Lint, strict type checks (Python and TypeScript) and the tests: **180 passed, 0 failed**, 4 deselected (the live Mac-app tests), 13 seconds.

| Group | Tests | Result |
|---|---|---|
| Contract (shapes, interfaces, live-run output guard) | 25 | pass |
| Demo data (D1 to D6) | 9 | pass |
| Local API (token, Origin, Host, click path) | 27 | pass |
| Consent and instant revoke | 10 | pass |
| Folder access (U1, U2, Unicode paths) | 12 | pass |
| Mac app connectors (read-only by construction) | 14 | pass |
| Readers (U8) | 10 | pass |
| Answer path (U3, U4, U7, U10, salary case) | 14 | pass |
| Model gateway and import allowlist | 16 | pass |
| Search without an index | 8 | pass |
| Proof panel (connections, fingerprint, zero writes) | 8 | pass |
| Memory, End session, Prepare, Coverage | 14 | pass |
| Pictures (reading, text recognition) | 7 | pass |
| Launch (real process, `127.0.0.1` only) and window | 4 | pass |
| Scaffold | 2 | pass |

Which test proves which promise: [traceability](traceability.md).

## 2. Evaluation with the real model

Eight tuning questions scored against the ground truth in `eval/`, story clock 22 Nov 2026 19:00. Three runs.

| Question | 65-file laptop | 143-file laptop (run 1) | 143-file laptop (run 2) |
|---|---|---|---|
| Q01 What did I promise Sam? | fail | fail | fail |
| Q02 What salary did I promise Sam? | pass | pass | pass |
| Q03 Is the February conference still happening? | pass | pass | pass |
| Q04 What is still open with Sam? | fail | fail | fail |
| Q05 Did HR approve the money for Sam's course? | pass | pass | pass |
| Q06 What do my notes say about Alex's performance? | pass | fail | fail |
| Q07 Ideas for the offsite? | pass | fail | fail |
| Q08 What did I promise Alex? | fail | pass | pass |
| **Passed** | **5 of 8** | **4 of 8** | **4 of 8** |

What the failures are:

- **Q01, Q04 (Sam):** the course point is reported as "open" where the ground truth says done, and the monthly career chat is missing from "still open". Same in all three runs.
- **Q06 on the 143-file laptop:** the answer cites one point ("Alex covering on Tuesday") where "not found" is expected. The private note was not opened.
- **Q07 on the 143-file laptop:** the model returned output the program could not use (error E-303), twice. The answer is "nothing", where the offsite note is expected.
- **Q08 on the 65-file laptop:** only 5 items passed the relevance rule and the expected note was not among the cited ones.

**Compared with before:** the README had 7 of 8 (two runs) and the status file 6 of 8. Both are higher than today's result. Prompts and data changed in between (the rich demo laptop and seven more pictures were added) and the evaluation was not re-run after those changes until now, so the cause is not isolated. It was not investigated further.

The held-out set (12 questions) was **not run**: it is kept for the final comparison and is never tuned on.

Time per question: 9 to 47 seconds.

## 3. Not run in this report

| Item | State |
|---|---|
| Wi-Fi-off run | Done by hand while the demo video was recorded; not repeated here |
| Live tests against the real Mac apps (`make test-live`) | Not run: they open the user's own Calendar, Mail, Notes and Reminders |
| Canary leak tests on the whole flow (L-1, L-5, L-6, L-7) | Not written |
| `verify` script (a check from outside the app after it quits) | Not built |
| Automated check that the page makes no outside request (N-3) | Not written; the content-security-policy forbids it |
| Handwriting and poor photos | Not tested |
| Windows | Not tested |
