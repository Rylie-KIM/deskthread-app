# Privacy promises and how to check them

[Back to the README](../README.md)

## The one rule, and what backs it today

| Promise | How it is upheld | Test |
|---|---|---|
| Nothing it reads leaves the device | One module may open a connection, and it refuses any address but `127.0.0.1`; no proxy is used; the model runs locally with cloud features off | gateway tests, import allowlist test |
| It keeps no copy | No database, index or temp-file library is imported; files are opened read-only; reading leaves the folder byte-identical; the tools write no cache or bytecode | U6, "connector never changes the folder" |
| You choose what it sees, and can change your mind | Every source starts Off, personal chat apps included; one switch allows reading, the same switch stops it; stopping cancels a read in progress and drops that source from memory. Nothing is ticked until you tick it, and Calendar and Mail are read only for the period you choose. Reading is the only permission: the Mac app scripts contain read commands only | consent tests, R2 read-only scan |
| Off-limits stays off-limits | The real path of every file is checked before it is opened; `..` and symlinks out of the chosen folder are refused; a `Personal` folder, a `PRIVATE…` file or a folder holding `.deskthread-off-limits` is never opened | U1, U2 |
| It is honest | The model returns a note id and a line number; code copies the quote, so a quote cannot be invented; a quote on another subject is rejected; nothing left means "not found" | U3, salary case |
| Notes are data, not orders | Lines that read like instructions to an assistant are withheld from the model and can never be cited | U4 |

## Check it yourself

DeskThread is built so that you can see what it does and stop it, instead of being asked to trust it. Each claim below says how DeskThread counts it and how you can check it without DeskThread.

| Claim | How DeskThread counts it | How you check it yourself |
|---|---|---|
| **It only reads** | "Read" is the only permission that exists in the app. The part that talks to a source has no function for writing. A test fails the build if a command that writes, sends, moves or deletes appears in what is sent to the Mac apps (`tests/unit/test_mac_apps.py`, the R2 scan) | Read the scripts in `app/sources/mac.py`: they contain `get`-style commands only. Run `make check`. One separate set of scripts (`app/sources/mac_show.py`) runs only when you press "Show in Notes" and the like: it brings the app forward and makes it display one item, and changes nothing the app holds |
| **Nothing was sent to the internet** | It asks macOS for the open connections of its own programs (`lsof -nP -iTCP -a -p <its process numbers>`). `127.0.0.1` is the Mac talking to itself; any other address is marked "Outside" | **My data → Check it now** shows what macOS printed, explains how to read it and gives the command with a Copy button. Paste it into Terminal: every line must contain `127.0.0.1`. Or switch Wi-Fi off: DeskThread keeps answering |
| **DeskThread saved nothing** | From launch, Python reports every file the program opens (an audit hook). If a file is opened for writing, creating or adding, a counter goes up. The target is 0 and the real number is shown on the receipt | The folder comparison below. Also: no DeskThread folder appears in `~/Library/Application Support`, and the window is set to keep no history, cache or cookies |
| **Your files are untouched** | When you choose a folder, the name, size and changed-time of every file in it are kept in memory (no file is opened). The same listing is taken again and compared | **My data** shows "Same" or "Changed" per folder and lists the files that were added, changed or removed, with the time. In Finder, sort the folder by "Date Modified" |
| **Memory is cleared** | After **Clear memory** or **End session** the pop-up ticks each step only when it is confirmed: no items held, no AI model loaded, the programs stopped | Open Activity Monitor and search for "DeskThread", "Python" and "ollama": after End session they are gone |
| **You decide what it reads** | Every source starts Off. Nothing is ticked in the permission pop-up until you tick it. Switching off stops a read in progress and drops that source from memory | **My data → What happened** lists what you allowed, what was read and how many items, with the time |

What these checks cannot show, said plainly:

- "Saved" and "Sent" are counted by DeskThread itself. That is why each has a check that does not depend on it.
- The connection list is a snapshot, so a very short connection could be missed. Wi-Fi off is the stronger check.
- macOS records the time and the account of a file change, not the app. A change in your folder is attributed to "you or another app" because DeskThread's own write count is 0, not because macOS names the app.
- The write count covers DeskThread's own program. The AI server is a separate program; the one thing it keeps on the Mac is an AI model you chose to download.
- Erasing memory cannot be proven from inside an app: freed memory and swap belong to the operating system.
- An independent `verify` script (a check from outside the app after it has quit) is not built.
