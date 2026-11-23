# Status

[Back to the README](../README.md)

## Status (22 November 2026)

This is a work in progress. The table says plainly what exists.

| Part | State |
|---|---|
| `DeskThread.app`: double-click start in its own Mac window (no browser, nothing kept), first-start setup | **Built**; opened and used on the development Mac; the first-start setup branches were not all exercised |
| Access: apps on the Mac (Calendar, Mail, Notes, Reminders) and folders, everything Off, read only, a period for Calendar and Mail | **Built and tested**; timed on the real apps (counts only) |
| Ask: answers with exact quotes, status, "possibly related" notes kept apart, an AI summary checked against the quotes, Stop, Prepare for a meeting, "how this was checked" with every number opening its items | **Built and tested** with a fake model; run with the real model on the invented data |
| Search: words, meaning (a small local search model, optional), time; dates by the file's own Date Modified | **Built and tested** |
| My data: connections of its own programs (Check it now), folder comparison, the log, memory by program; Clear memory; End session with a receipt that says how each number is counted | **Built and tested** |
| Pictures: the text is read by macOS's own text recognition when switched on, the AI only for pictures without text | **Built and tested** on typed pictures; handwriting not tested |
| AI model page: eight models with parameters and download size, a search helper | **Built**; only three models were run with DeskThread; downloads of the other five were not run |
| Local API with a per-launch token, Origin and Host checks, strict content-security-policy | **Built and tested** |
| The tuning evaluation on the invented data | **6 of 8** at the last full run; not re-run after the later changes |
| `verify` script (an independent check after quitting), canary leak test on the whole flow, Wi-Fi-off run | **Not built or not run yet** |
| Windows | **Not tested** |

