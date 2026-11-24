# Traceability: user need → feature → test

[Back to the README](../README.md) · [Test report](test-report.md)

**U** = a user need (what the manager needs). **F** = the feature that meets it. **T** = the automated test file that checks the feature.
Read a row left to right: a need, the features that serve it, and the tests that prove those features.

A feature with "none" has no automated test of its own; it is checked by hand or by the evaluation (see [Status](status.md)).

## U → F → T

| User need | Features | Tests |
|---|---|---|
| **UN-01** Before a one-to-one, I need to recall what I promised the person | FT-10 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **UN-02** I need to find my notes even when I wrote them in different words from the ones I search with | FT-08, FT-09 | [`unit/test_model_gateway.py`](../tests/unit/test_model_gateway.py), [`unit/test_search.py`](../tests/unit/test_search.py) |
| **UN-03** I need notes written weeks apart joined into one picture | FT-08, FT-10 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py), [`unit/test_search.py`](../tests/unit/test_search.py) |
| **UN-04** I need to see which note and which exact words each answer came from, and when it was written | FT-10, FT-12, FT-14, FT-20 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py), [`unit/test_api.py`](../tests/unit/test_api.py) |
| **UN-05** I need it to cope with messy notes (fragments, no date, vague titles) | FT-04, FT-11 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py), [`unit/test_readers.py`](../tests/unit/test_readers.py) |
| **UN-06** I need to be told when a newer note changes an older one | FT-11, FT-10 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **UN-07** I need an honest "I could not find it" instead of an invented answer | FT-12 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **UN-08** I need to choose what it can see and change my mind | FT-01, FT-02, FT-03, FT-15 | [`unit/test_consent.py`](../tests/unit/test_consent.py), [`unit/test_folder_access.py`](../tests/unit/test_folder_access.py) |
| **UN-09** I need to be sure my notes stay on my laptop and the assistant keeps nothing | FT-09, FT-16, FT-22, FT-23, FT-28 | [`network/test_launch.py`](../tests/network/test_launch.py), [`unit/test_api.py`](../tests/unit/test_api.py), [`unit/test_ending.py`](../tests/unit/test_ending.py), [`unit/test_model_gateway.py`](../tests/unit/test_model_gateway.py), [`unit/test_proof.py`](../tests/unit/test_proof.py) |
| **UN-10** I need to check that myself, without trusting the developer | FT-17, FT-18, FT-19, FT-20, FT-22 | [`unit/test_proof.py`](../tests/unit/test_proof.py) |
| **UN-11** I need it to cover the places I keep work information: notes, email, calendar, tasks, chats | FT-01, FT-04, FT-05, FT-06, FT-07a | [`unit/test_folder_access.py`](../tests/unit/test_folder_access.py), [`unit/test_readers.py`](../tests/unit/test_readers.py) |
| **UN-12** I need to keep my private apps and folders out of reach until I decide to open them | FT-02, FT-03 | [`unit/test_consent.py`](../tests/unit/test_consent.py), [`unit/test_folder_access.py`](../tests/unit/test_folder_access.py) |
| **UN-13** I need to use it like any app, without being a developer | FT-24, FT-25 | [`network/test_launch.py`](../tests/network/test_launch.py), [`unit/test_window.py`](../tests/unit/test_window.py) |
| **UN-14** I need to stay in charge: confirm or correct what it found before relying on it | FT-21 | none |
| **UN-15** I need it not to be fooled by text inside a note that gives it orders | FT-13, FT-12 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **UN-16** I need an answer fast enough to use before a meeting | FT-08, FT-31 | [`unit/test_search.py`](../tests/unit/test_search.py) |
| **UN-17** I need it to look trustworthy and consistent with the client's style | FT-25 | none |
| **UN-18** (Stakeholder: AI Studio standards team) I need to run, read and verify the work | FT-26, FT-27, FT-29 | none |
| **UN-19** I need the assistant to keep nothing about my notes after the session, to see what it holds in memory right now, and to make it forget at once | FT-35 | [`unit/test_memory.py`](../tests/unit/test_memory.py) |
| **UN-20** I need it to know which meeting I am preparing for without me retyping it ("tomorrow I have a one-to-one with Sam") | FT-34 | [`unit/test_prepare.py`](../tests/unit/test_prepare.py) |
| **UN-21** I need to see which files it looked at and which it did not, for every answer | FT-36 | [`unit/test_coverage.py`](../tests/unit/test_coverage.py) |
| **UN-22** I need to give access with one click and take it back instantly, for each source | FT-53, FT-15, FT-02 | [`unit/test_consent.py`](../tests/unit/test_consent.py) |
| **UN-23** I need to open the original note, file, reminder or calendar day behind a quote, to judge it in its own context | FT-54 | [`unit/test_api.py`](../tests/unit/test_api.py) |
| **UN-24** I need to see how an answer was reached, step by step, and open every number to see the items behind it | FT-55 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **UN-25** I need notes that may be related, but do not name the person, shown apart and never mixed into the confirmed points | FT-56 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py), [`unit/test_search.py`](../tests/unit/test_search.py) |
| **UN-26** I need to choose how far back Calendar and Mail are read | FT-57 | none |
| **UN-27** I need to stop a long question and see how far it has got | FT-58, FT-59 | [`unit/test_api.py`](../tests/unit/test_api.py), [`unit/test_images.py`](../tests/unit/test_images.py) |
| **UN-28** I need to choose which AI model answers, and see its size and what it fits | FT-60 | [`unit/test_api.py`](../tests/unit/test_api.py), [`unit/test_model_gateway.py`](../tests/unit/test_model_gateway.py) |

## F → U, T

| Feature | Serves | Tests |
|---|---|---|
| **FT-01** Source scanner | UN-08, UN-11, UN-12 | [`unit/test_folder_access.py`](../tests/unit/test_folder_access.py) |
| **FT-02** Source panel, default deny, with a permission request per source | UN-08, UN-12, UN-09, UN-22 | [`unit/test_consent.py`](../tests/unit/test_consent.py) |
| **FT-03** Never-read list / off-limits marker for folders and single files | UN-12, UN-08 | [`unit/test_folder_access.py`](../tests/unit/test_folder_access.py) |
| **FT-04** Reader | UN-05, UN-11 | [`unit/test_readers.py`](../tests/unit/test_readers.py) |
| **FT-05** Reader | UN-11 | [`unit/test_readers.py`](../tests/unit/test_readers.py) |
| **FT-06** Readers | UN-11 | [`unit/test_readers.py`](../tests/unit/test_readers.py) |
| **FT-39** Image reader | UN-11, UN-04 | [`unit/test_images.py`](../tests/unit/test_images.py) |
| **FT-07** Readers | UN-11 | [`unit/test_readers.py`](../tests/unit/test_readers.py) |
| **FT-08** Candidate selection with no stored index | UN-02, UN-03, UN-16 | [`unit/test_search.py`](../tests/unit/test_search.py) |
| **FT-09** Local model gateway | UN-02, UN-09, UN-10 | [`unit/test_model_gateway.py`](../tests/unit/test_model_gateway.py) |
| **FT-10** Brief | UN-01, UN-03, UN-04, UN-06 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **FT-11** Messy-note handling | UN-05, UN-06 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **FT-12** Answer gate | UN-04, UN-07, UN-15 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **FT-13** Injection handling | UN-15 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **FT-14** Source viewer | UN-04 | [`unit/test_api.py`](../tests/unit/test_api.py) |
| **FT-15** Stop access / instant revoke | UN-08, UN-09, UN-22 | [`unit/test_consent.py`](../tests/unit/test_consent.py) |
| **FT-16** End session | UN-09, UN-10 | [`network/test_launch.py`](../tests/network/test_launch.py), [`unit/test_ending.py`](../tests/unit/test_ending.py) |
| **FT-17** Proof panel | UN-10, UN-09 | [`unit/test_proof.py`](../tests/unit/test_proof.py) |
| **FT-18** Proof panel | UN-10, UN-09 | [`unit/test_proof.py`](../tests/unit/test_proof.py) |
| **FT-19** Proof panel | UN-10 | [`unit/test_proof.py`](../tests/unit/test_proof.py) |
| **FT-20** Gate trace line under each answer | UN-10, UN-04, UN-14 | none |
| **FT-21** Human confirmation of each item (not built) | UN-14 | none |
| **FT-22** Settings file and "what I saved" view | UN-09, UN-10 | [`unit/test_proof.py`](../tests/unit/test_proof.py) |
| **FT-23** Local API protection | UN-09 | [`unit/test_api.py`](../tests/unit/test_api.py) |
| **FT-24** One-click launcher and clean stop | UN-13 | [`network/test_launch.py`](../tests/network/test_launch.py), [`unit/test_window.py`](../tests/unit/test_window.py) |
| **FT-25** UI in the client's visual style | UN-13, UN-17 | none |
| **FT-26** Evaluation harness and model comparison | UN-16, UN-07, UN-18 | none |
| **FT-27** README, architecture picture, run steps, Windows porting notes | UN-18 | none |
| **FT-28** Telemetry off and offline mode | UN-09 | none |
| **FT-29** Mock laptop generator and ground truth | UN-18 | none |
| **FT-30** Save a copy of the brief (dropped) | UN-01 | none |
| **FT-31** Speed | UN-16 | none |
| **FT-32** Closest notes after "not found" (dropped) | UN-07, UN-04 | none |
| **FT-33** Native "Choose folder..." button | UN-13, UN-08 | [`unit/test_api.py`](../tests/unit/test_api.py) |
| **FT-34** "Prepare my next meeting" | UN-20, UN-01, UN-03, UN-08, UN-12 | [`unit/test_prepare.py`](../tests/unit/test_prepare.py) |
| **FT-35** Memory by program in "My data" and "Clear memory" (called "Forget now" in the plan) | UN-19, UN-09, UN-10 | [`unit/test_memory.py`](../tests/unit/test_memory.py) |
| **FT-36** Coverage view for every answer | UN-21, UN-10, UN-07 | [`unit/test_coverage.py`](../tests/unit/test_coverage.py) |
| **FT-37** Memory evidence (the worker process is not built) | UN-19, UN-10, UN-09 | [`unit/test_memory.py`](../tests/unit/test_memory.py) |
| **FT-38** Download page | UN-13, UN-18 | none |
| **FT-40** End-session receipt | UN-09, UN-10, UN-19 | [`unit/test_ending.py`](../tests/unit/test_ending.py) |
| **FT-41** `verify` script, separate from the app, run by the user before and af… (not built) | UN-10, UN-09 | none |
| **FT-42** Web hardening | UN-09, UN-15 | [`unit/test_api.py`](../tests/unit/test_api.py) |
| **FT-43** Path confinement | UN-08, UN-12 | [`unit/test_folder_access.py`](../tests/unit/test_folder_access.py) |
| **FT-44** The model has no tools | UN-09, UN-15 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **FT-45** Runtime and supply-chain settings | UN-09, UN-18 | [`unit/test_model_gateway.py`](../tests/unit/test_model_gateway.py) |
| **FT-46** Crash and browser traces | UN-09, UN-10 | none |
| **FT-47** Worker sandbox (not built) | UN-09, UN-10 | none |
| **FT-48** Apple Notes connector | UN-11, UN-08, UN-09 | [`unit/test_mac_apps.py`](../tests/unit/test_mac_apps.py) |
| **FT-49** Calendar connector | UN-20, UN-11, UN-12 | [`unit/test_mac_apps.py`](../tests/unit/test_mac_apps.py) |
| **FT-50** Mail connector | UN-11, UN-08 | [`unit/test_mac_apps.py`](../tests/unit/test_mac_apps.py) |
| **FT-51** Demo seeder | UN-18 | none |
| **FT-52** Reminders connector | UN-11, UN-08 | [`unit/test_mac_apps.py`](../tests/unit/test_mac_apps.py) |
| **FT-53** Permission broker | UN-22, UN-08, UN-09, UN-12 | [`unit/test_consent.py`](../tests/unit/test_consent.py) |
| **FT-54** Show in its own app: the viewer bar opens the file in Finder, the note in Notes, the reminder in Reminders, the day in Calendar (Mail only opens the app) | UN-23, UN-04 | [`unit/test_api.py`](../tests/unit/test_api.py) |
| **FT-55** "How this was checked": a funnel of items read, looked related, notes quoted and things found; the model's name; "Left out" in plain sentences; every number opens its items | UN-24, UN-10, UN-21 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) |
| **FT-56** Search by meaning (a small local search model, in memory only) and by time, a second wider search when the first finds nothing, and the "Possibly related" group | UN-25, UN-02, UN-03 | [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py), [`unit/test_search.py`](../tests/unit/test_search.py) |
| **FT-57** Period for Calendar and Mail ("Most recent" 2 weeks to 1 year, or exact dates) | UN-26, UN-08 | none |
| **FT-58** Stop: cuts the running question, including the request that is with the AI | UN-27 | [`unit/test_api.py`](../tests/unit/test_api.py) |
| **FT-59** Pictures read in the background with macOS text recognition, with "picture n of m" progress; the AI only for pictures without text | UN-27, UN-11 | [`unit/test_images.py`](../tests/unit/test_images.py), [`unit/test_ocr.py`](../tests/unit/test_ocr.py) |
| **FT-60** AI model page: eight approved models with parameters, download size and when each fits, plus the search helper card | UN-28, UN-13 | [`unit/test_api.py`](../tests/unit/test_api.py), [`unit/test_model_gateway.py`](../tests/unit/test_model_gateway.py) |

## Planned, not built

These features were planned (`plan/plan.md`, section 19) and are **not in the app**. They have no code and no test, so the needs they were meant to serve are only partly met.

| Feature | Planned for | Why it matters |
|---|---|---|
| **FT-21** Human confirmation of each item | UN-14 | UN-14 ("stay in charge: confirm or correct") has no feature yet; the source viewer lets the user check each quote by hand |
| **FT-41** Independent `verify` script | UN-10, UN-09 | The user can check with "Check it now" and the folder comparison, but there is no separate script |
| **FT-47** Worker sandbox (network denied by the operating system) | UN-09, UN-10 | Not built; the claim "reads with no network" rests on the code and tests, not on the operating system |
| Worker process for note handling (part of FT-37) | UN-19 | Not built; the Memory panel and Clear memory work in the main backend process |
| **FT-30** Save a copy of the brief | UN-01 | Dropped: the app writes nothing to disk |
| **FT-32** Closest notes after "not found" | UN-07 | Dropped as a separate screen; the second, wider search and "Possibly related" cover part of it |

## T → F

| Test file | Tests | Features |
|---|---|---|
| [`contract/test_contracts.py`](../tests/contract/test_contracts.py) | 9 | (shared checks) |
| [`contract/test_redact.py`](../tests/contract/test_redact.py) | 5 | (shared checks) |
| [`data/test_demo_data.py`](../tests/data/test_demo_data.py) | 9 | (shared checks) |
| [`live/test_mac_apps_live.py`](../tests/live/test_mac_apps_live.py) | 1 | (shared checks) |
| [`network/test_launch.py`](../tests/network/test_launch.py) | 1 | FT-16, FT-24 |
| [`test_scaffold.py`](../tests/test_scaffold.py) | 2 | (shared checks) |
| [`unit/test_answer_pipeline.py`](../tests/unit/test_answer_pipeline.py) | 14 | FT-10, FT-11, FT-12, FT-13, FT-44, FT-55, FT-56 |
| [`unit/test_api.py`](../tests/unit/test_api.py) | 27 | FT-14, FT-23, FT-33, FT-42, FT-54, FT-58, FT-60 |
| [`unit/test_consent.py`](../tests/unit/test_consent.py) | 10 | FT-02, FT-15, FT-53 |
| [`unit/test_coverage.py`](../tests/unit/test_coverage.py) | 2 | FT-36 |
| [`unit/test_ending.py`](../tests/unit/test_ending.py) | 4 | FT-16, FT-40 |
| [`unit/test_folder_access.py`](../tests/unit/test_folder_access.py) | 12 | FT-01, FT-03, FT-43 |
| [`unit/test_images.py`](../tests/unit/test_images.py) | 4 | FT-39, FT-59 |
| [`unit/test_mac_apps.py`](../tests/unit/test_mac_apps.py) | 14 | FT-48, FT-49, FT-50, FT-52 |
| [`unit/test_memory.py`](../tests/unit/test_memory.py) | 4 | FT-35, FT-37 |
| [`unit/test_model_gateway.py`](../tests/unit/test_model_gateway.py) | 12 | FT-09, FT-45, FT-60 |
| [`unit/test_ocr.py`](../tests/unit/test_ocr.py) | 3 | FT-59 |
| [`unit/test_prepare.py`](../tests/unit/test_prepare.py) | 4 | FT-34 |
| [`unit/test_proof.py`](../tests/unit/test_proof.py) | 8 | FT-17, FT-18, FT-19, FT-22 |
| [`unit/test_readers.py`](../tests/unit/test_readers.py) | 10 | FT-04, FT-05, FT-06, FT-07 |
| [`unit/test_search.py`](../tests/unit/test_search.py) | 8 | FT-08, FT-56 |
| [`unit/test_window.py`](../tests/unit/test_window.py) | 3 | FT-24 |
