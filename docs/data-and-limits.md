# Demo data and limitations

[Back to the README](../README.md)

## Data

All sample content is invented: a fictional company ("UK Pharma"), a fictional manager and a team of four. The demo laptop is built by `demo-data/make_demo_data.py`: 65 files in its first layer (`make demo-data-core`, what the tests and the evaluation use) and 143 in its rich version (`make demo-data`). The expected answers are kept in `eval/`, outside the folder the assistant can read. No real notes were used.

## Limitations

- **Dates.** A note, document, PDF, chat export or picture file is dated by the file's own "Date Modified"; a note in the Notes app by the time the app says it was last changed. A mail keeps its header date, a calendar entry its start and a reminder its due date. A file that was copied or re-saved therefore carries the time of that copy, not the day it was first written. Dates written in Korean are not recognised in questions; "today", "tomorrow", "this week" and similar English words are.

- The answer check proves that a quote exists in the cited note and is on the subject. It cannot prove the quote means what the writer meant.
- The text of a picture is read by **macOS's own text recognition** (Apple Vision), in memory, when you switch Pictures on; only where it finds no text is the answering AI asked to look, and only if it can read pictures. A quote from an image matches that **reading** of the image, not the pixels. Typed screenshots were tested; handwriting and poor photos were not.
- The model suggests search words and can miss a line (see the failing question above).
- Between questions, the items of allowed sources stay in the backend's memory until you revoke a source, forget, or end the session. Erasing memory contents cannot be proven; swap and hibernation files are outside the app's control.
- macOS has no read-only permission for calendars: to read events an app must ask for "Full Access" (the only other choice, "Add Only", cannot read). DeskThread uses fetch calls only, and a test fails if a call that saves or removes an event appears in the code. If you refuse, the slower scripting route is used.
- The other Mac app connectors read through each app's scripting interface. macOS words that permission as "control", not "read only"; DeskThread sends read commands only, and a test fails on any command that writes, sends, moves or deletes. Calendar is slow through this route (25 to 84 seconds across eight calendars in a test), so tick only the calendars you need; Mail reads the newest 25 messages of one mailbox, as far as Mail has them on this Mac. The connectors were timed on the real apps with counts only (Notes 50 notes in 0.4 s, Reminders 55 items in 10 s, Mail 25 messages in 38 s); answer quality on real app content has not been measured.
- Only the default model has been run through DeskThread's tests. The other two models are offered untested: answer quality, picture reading and the output format are not verified for them.
- Downloading a model is the one time the model server uses the internet; during it, "My data" will show an outside connection.
- The runtime does not offer forced JSON output for this model, so the model's JSON is validated in code and asked for once more if it is malformed.
- Windows is untested.

