"""Frozen contracts between the parts of DeskThread.

Everything here is an interface or a plain data shape. Only the main session changes this
package; a change bumps CONTRACT_VERSION (dev rule R14).
"""

# 1.1 demo folder; 1.2 no locked sources; 1.3 models; 1.4 progress; 1.5 status; 1.6 folders;
# 1.7 a period for app sources, app icons; 1.8 stop a question, progress detail, folder counts
# 1.9 an exact date range for app sources, a summary and "matched" words on answers
# 1.10 the connection check, run for the user and shown as macOS printed it
# 1.11 show the original of an item (in Finder, or its app)
# 1.12 the Mac's free memory, measured
# 1.13 an answer names its AI model and counts what was left out
# 1.14 the search model; points that are only possibly related
# 1.15 other spellings of a name
# 1.16 the log records choosing and removing a folder
# 1.17 a source can be blocked by the AI model in use (pictures)
# 1.18 a model states how many parameters it has
# 1.19 an answer lists the items of each stage and what was left out
CONTRACT_VERSION = "1.19"
