# Tests

[Back to the README](../README.md)

## Tests

`make check` runs lint, strict type checks (Python and TypeScript) and 183 tests in about 13 seconds, without the model.

| Group | What it proves | Result |
|---|---|---|
| Contract | item shape, interfaces, API shapes, error codes; the live-run guard blocks a planted canary and a sample title | pass |
| Data (D1 to D6) | the searched phrase appears nowhere; all addresses use `.example`; rebuilds are byte-identical; nothing supports a pay promise | pass |
| Access (U1, U2, Unicode paths) | off-limits and outside files are never opened, also by name, `..` or symlink | pass |
| Consent | default Off, chat apps included; allow then stop; stop during a read; turn everything off; reading is the only permission | pass |
| Readers (U8) | each file type gives text, a title and the writer's date; broken and unsupported files are counted | pass |
| Model gateway (U6) | loopback only; pinned digest; unload verified against a fake server; no database or index library | pass |
| Answer path (U3, U4, U7, U9, U10) | invented citations dropped; injection withheld; superseded and undated handled; coverage adds up; a deleted note is gone at once | pass, with a scripted fake model |
| Local API (U5) | no token, wrong Origin or wrong Host is refused; replies are not stored; only the page's own start-up script may run | pass |
| Proof, memory, end session | local-only connections, fingerprint without opening files, zero writes (L-4), Clear memory, receipt without note text | pass |
| Launch (N-6) | the real process listens on `127.0.0.1` only, needs the token, and refuses connections after End session | pass |
| Evaluation with the real model | tuning set against the ground truth | 5 of 8 (65 files), 4 of 8 (143 files); see the [test report](test-report.md) |
| Click path, by hand | earlier design: choose folder, permission request, Prepare, source viewer, Proof, End session, with the real model. Current design: the Access screen and the one-click demo only | the Ask and My data screens, the model card, the end-session pop-up and "Start a new session" have **not** been looked at since the redesign |

The Wi-Fi-off run (N-2) was done by hand while the demo video was recorded; it is not repeated in the test report and has no automated test. Not written or not run yet: the canary leak tests on the full flow (L-1, L-5, L-6, L-7), and an automated check that the page makes no outside request (N-3; today the content-security-policy forbids it).

