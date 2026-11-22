"""More of the invented demo laptop: the second layer of the same story.

The first layer (content.py) holds the story the tests and the evaluation depend on: the
five promises to Sam, the injection note, the private files. This layer adds the rest of a
working life around it: stand-ups and retros, hiring, a dashboard vendor, the offsite, the
QBR deck, launch sign-off, on-call, mail, chats, transcripts, spreadsheets and pictures.

Rules that the tests enforce for every text file (see tests/data/test_demo_data.py):
no "development" or "goal(s)", no pay words, every address on the .example domain. Sam
appears only in a few files, so the five promises stay findable.
"""

from content import ME

NOTES = "App-exports/Notes"
MAIL = "App-exports/Mail"

# --------------------------------------------------------------------------- notes
NOTE_FILES: dict[str, str] = {
    f"{NOTES}/retro-oct.md": """\
Team retro
Fri 30 Oct 2026

keep: short release cycles, the Friday demo
stop: ad hoc requests that skip the queue
start: a written decision log, owner named for every action
mood: tired but proud after the October release
""",
    f"{NOTES}/lee-onboarding.md": """\
Lee onboarding plan
Mon 26 Oct 2026

week 1: laptop, access, meet the platform team, read the launch checklist
week 2: pair with Sam on the checklist, join stand-up
week 3: own one checklist section, first 1:1
week 4: review: what was confusing? write it down for the next hire
""",
    f"{NOTES}/hiring-analyst-notes.md": """\
Analyst role - plan
Mon 2 Nov 2026

what we need: someone who likes messy data and explains it simply
must: SQL, a charting tool, curiosity
nice: pharma or lab data, some Python
process: screen with recruiting, one technical chat, one panel with me, Mark and Jo
decision meeting is Fri 13 Nov (final three on the board)
""",
    f"{NOTES}/standup-notes-wk44.md": """\
Stand-up notes
Mon 2 Nov 2026

- checklist v1 drafted, review Wednesday
- vendor quote still missing the support terms
- Alex out Friday
- offsite: venue shortlist by end of the week
""",
    f"{NOTES}/hiring-data-engineer-notes.md": """\
Data engineer role - plan
Mon 9 Nov 2026

what we need: someone who writes things down and likes pipelines
must: Python, SQL, version control
panel: me, Mark, Lee
questions in the shared interview folder
phone screens start 30 Nov, interviews 1 to 3 Dec
""",
    f"{NOTES}/vendor-quote-notes.md": """\
LabViz dashboard quote
Mon 9 Nov 2026

quote: 4,200 a year for the lab dashboard, ten seats
support: business hours only, reply "next working day"
want in writing: 24 hour response for critical issues
compare with building it ourselves before Q1 planning
""",
    f"{NOTES}/launch-readiness-risks.md": """\
Launch readiness - risks
Tue 10 Nov 2026

1. field training deck late (Jo says Monday)
2. checklist has two owners and nobody decides (Sam and Lee)
3. vendor support terms not agreed
4. release freeze overlaps the all-hands
sign-off meeting is Wed 18 Nov
""",
    f"{NOTES}/data-quality-talk.md": """\
Lunch-and-learn: data quality
Wed 11 Nov 2026

Jo wants to give the talk. Topics: missing values, units, the three checks every
analyst should run before a chart leaves the team.
date: Thu 3 Dec, 12:30, room 5. Lunch ordered by the team lunch budget.
""",
    f"{NOTES}/standup-notes-wk45.md": """\
Stand-up notes
Mon 9 Nov 2026

- Lee finished checklist section two
- Jo drafting QBR deck v1, will send tomorrow
- Alex asks about the on-call swap, agreed for December
- vendor demo booked for Wed 18 Nov
""",
    f"{NOTES}/qbr-feedback-jo.md": """\
Feedback for Jo - QBR deck
Thu 12 Nov 2026

good: clear story, the chart on slide 4
change: fewer words per slide, one message each
change: add the data quality numbers
to do: send this to Jo by Tue 24 Nov, deck is due Mon 30 Nov
""",
    f"{NOTES}/interview-questions.md": """\
Interview questions (shared)
Fri 13 Nov 2026

1. Tell me about a time the data was wrong. What did you do?
2. How do you explain a chart to someone who dislikes charts?
3. What do you do when two numbers disagree?
4. What would you want to learn in your first three months?
same questions for everyone, score each one 1 to 4
""",
    f"{NOTES}/one-to-one-structure.md": """\
How I run a one-to-one
Sat 14 Nov 2026

1. their topics first, mine second
2. what is blocked?
3. one thing they are proud of
4. write down what I promised, the same day
never cancel, move it
""",
    f"{NOTES}/weekend-thoughts.md": """\
Weekend thoughts
Sun 15 Nov 2026

too many things start with "I'll set it up"
write the promise down the same day
Friday is for follow-ups, not new work
S needs a visible win before the new year
""",
    f"{NOTES}/qbr-outline.md": """\
QBR deck outline
Mon 16 Nov 2026

1. what we shipped (launch readiness, the dashboard refresh)
2. what the data says (Jo: data quality slide)
3. what we learned (retro points)
4. what we need next quarter (headcount, vendor decision, training budget)
due Mon 30 Nov 09:00
""",
    f"{NOTES}/offsite-logistics.md": """\
Offsite logistics
Tue 17 Nov 2026

venue: Engine Shed, held for 14 Jan until Fri 27 Nov
people: 18, budget 85 per head (Finance confirmed)
catering: lunch plus an evening meal, one vegan and two gluten free
travel: train, tickets booked by each person, claim in expenses
""",
    f"{NOTES}/questions-i-keep-asking.md": """\
Questions I keep asking
Tue 17 Nov 2026

who owns the checklist?
is the vendor support promise written anywhere?
what does the training budget really allow?
what is the one thing we would drop if we had to?
""",
    f"{NOTES}/vendor-demo-notes.md": """\
LabViz demo
Wed 18 Nov 2026

nice charts, vague about support
price is fine if the response time is written in
ask for two reference customers
the in-house option would take about a quarter
""",
    f"{NOTES}/launch-signoff-notes.md": """\
Launch sign-off
Wed 18 Nov 2026

decision: go, with one condition: field training deck on Monday
actions: Jo - deck Monday. Lee - freeze the checklist. Alex - on-call for the release week
checklist owner: shared for now, decide in January
""",
    f"{NOTES}/vendor-comparison.md": """\
Dashboard options
Thu 19 Nov 2026

LabViz: 4,200 a year, fast to start, support is business hours
in-house: no licence, about a quarter of two people's time
criteria: speed, support, data stays on our servers, who maintains it
leaning: LabViz if the support terms are written in, otherwise in-house
""",
    f"{NOTES}/offsite-agenda-draft.md": """\
Offsite agenda - draft
Fri 20 Nov 2026

09:30 arrival and coffee
10:00 look back: what worked this year
11:00 workshop: what to drop, what to keep
12:30 lunch
14:00 team plan for Q1
17:30 dinner
""",
    f"{NOTES}/delegation-notes.md": """\
Notes on delegating
Sat 21 Nov 2026

give the outcome, not the steps
check in at the halfway point, not every day
praise in public, adjust in private
if I keep redoing it, I did not delegate it
""",
    f"{NOTES}/field-training-notes.md": """\
Field training
Fri 6 Nov 2026

Jo owns the deck. Two sessions: one for the north team, one for the south team.
Slides must work without us in the room. Dates after sign-off.
""",
    f"{NOTES}/oncall-rota.md": """\
On-call rota
Mon 2 Nov 2026

week of 2 Nov: Jo
week of 9 Nov: Lee
week of 16 Nov: Jo
week of 23 Nov: Alex (swapped in, see the 10 Nov note)
week of 30 Nov: Lee
""",
    f"{NOTES}/open-loops-sunday.md": """\
Sunday review
Sun 22 Nov 2026

open loops: course link, intro date, roadmap follow-up, offsite venue
Monday starts with the one-to-one: bring the link and the intro date
send Jo the QBR feedback, deck due Mon 30 Nov
confirm the venue hold before Fri 27 Nov
""",
    f"{NOTES}/unsorted.md": """\
Unsorted
Sun 22 Nov 2026

dashboards -> ask the platform lead about a shared template
H.R. reply still pending
birthday card for the team
""",
    f"{NOTES}/standup-notes-wk46.md": """\
Stand-up notes
Mon 16 Nov 2026

- sign-off Wednesday, everyone free in the afternoon
- offsite budget confirmed by Finance
- Lee asks for a second pair of eyes on section four
- vendor demo moved to Wednesday morning
""",
}

# --------------------------------------------------------------------------- mail
MAILS_MORE: list[tuple[str, str, str, str, str, str]] = [
    (
        "2026-11-02_HR_booking_reminder.eml",
        "HR Learning <hr-learning@ukpharma.example>",
        ME,
        "Reminder: book approved courses through the portal",
        "Mon, 02 Nov 2026 09:00:00 +0000",
        "Hi Seoyeon,\n\nApproved courses must be booked through the learning portal by 18 December "
        "or the budget returns to the pool.\n\nKind regards,\nHR Learning\n",
    ),
    (
        "2026-11-03_Finance_offsite_budget.eml",
        "Priya Nair <priya.nair@ukpharma.example>",
        ME,
        "Offsite budget",
        "Tue, 03 Nov 2026 10:30:00 +0000",
        "Hi Seoyeon,\n\nFor the January offsite I can plan with 85 per head, up to 18 people. "
        "Please send the final headcount by 20 November.\n\nPriya\n",
    ),
    (
        "2026-11-04_Recruiting_analyst_shortlist.eml",
        "Dan Okafor <dan.okafor@ukpharma.example>",
        ME,
        "Analyst role: shortlist of three",
        "Wed, 04 Nov 2026 16:05:00 +0000",
        "Hi Seoyeon,\n\nThree candidates are through to the panel. Decision meeting on Friday "
        "13 November, room 3. Feedback forms are in the shared folder.\n\nDan\n",
    ),
    (
        "2026-11-05_LabViz_quote.eml",
        "LabViz Sales <sales@labviz.example>",
        ME,
        "Quote: LabViz lab dashboard, ten seats",
        "Thu, 05 Nov 2026 11:45:00 +0000",
        "Dear Seoyeon,\n\nPlease find our quote: 4,200 per year for ten seats. Support is "
        "included during business hours.\n\nBest regards,\nLabViz Sales\n",
    ),
    (
        "2026-11-06_LabViz_support_terms.eml",
        "LabViz Sales <sales@labviz.example>",
        ME,
        "RE: Quote - support terms",
        "Fri, 06 Nov 2026 15:20:00 +0000",
        "Dear Seoyeon,\n\nWe can offer a reply by the next working day. A 24 hour response for "
        "critical issues would need our premium plan.\n\nBest regards,\nLabViz Sales\n",
    ),
    (
        "2026-11-09_Jo_qbr_deck_v1.eml",
        "Jo <jo@ukpharma.example>",
        ME,
        "QBR deck v1",
        "Mon, 09 Nov 2026 17:40:00 +0000",
        "Hi Seoyeon,\n\nDeck v1 is in the shared folder. I am not sure about slide 6, can you "
        "have a look when you have a minute?\n\nJo\n",
    ),
    (
        "2026-11-10_Lee_checklist_draft.eml",
        "Lee <lee@ukpharma.example>",
        ME,
        "Launch checklist v2",
        "Tue, 10 Nov 2026 14:15:00 +0000",
        "Hi Seoyeon,\n\nChecklist v2 is ready. Section four still needs an owner. Sam and I "
        "split the rest.\n\nLee\n",
    ),
    (
        "2026-11-11_Alex_oncall_swap.eml",
        "Alex <alex@ukpharma.example>",
        ME,
        "On-call swap",
        "Wed, 11 Nov 2026 09:20:00 +0000",
        "Hi Seoyeon,\n\nThanks for agreeing the swap. I will cover the week of 23 November and "
        "Jo takes my December week.\n\nAlex\n",
    ),
    (
        "2026-11-12_IT_encryption_reminder.eml",
        "IT Service Desk <it@ukpharma.example>",
        ME,
        "Action needed: confirm disk encryption",
        "Thu, 12 Nov 2026 08:00:00 +0000",
        "Hello,\n\nPlease confirm disk encryption on your laptop by 27 November using the link "
        "in the staff portal.\n\nIT Service Desk\n",
    ),
    (
        "2026-11-13_Recruiting_interview_slots.eml",
        "Dan Okafor <dan.okafor@ukpharma.example>",
        ME,
        "Data engineer role: interview slots",
        "Fri, 13 Nov 2026 12:10:00 +0000",
        "Hi Seoyeon,\n\nPhone screens run on Monday 30 November, panel interviews from "
        "1 to 3 December. I have held room 5 for the mornings.\n\nDan\n",
    ),
    (
        "2026-11-16_Finance_headcount_confirmed.eml",
        "Priya Nair <priya.nair@ukpharma.example>",
        ME,
        "RE: Offsite budget",
        "Mon, 16 Nov 2026 13:00:00 +0000",
        "Hi Seoyeon,\n\nConfirmed: 85 per head for 18 people, 1,530 in total. Travel is claimed "
        "separately through expenses.\n\nPriya\n",
    ),
    (
        "2026-11-16_Venue_hold.eml",
        "Engine Shed Events <events@engineshed.example>",
        ME,
        "Your hold for 14 January",
        "Mon, 16 Nov 2026 15:50:00 +0000",
        "Dear Seoyeon,\n\nWe are holding the main room for 14 January until Friday 27 November. "
        "After that it returns to general availability.\n\nEngine Shed Events\n",
    ),
    (
        "2026-11-17_Alex_vendor_evaluation.eml",
        "Alex <alex@ukpharma.example>",
        ME,
        "Can I lead the vendor evaluation?",
        "Tue, 17 Nov 2026 15:35:00 +0000",
        "Hi Seoyeon,\n\nI would like to lead the dashboard vendor evaluation. I can have a first "
        "comparison ready by 4 December.\n\nAlex\n",
    ),
    (
        "2026-11-18_Lee_signoff_summary.eml",
        "Lee <lee@ukpharma.example>",
        ME,
        "Sign-off summary",
        "Wed, 18 Nov 2026 17:05:00 +0000",
        "Hi Seoyeon,\n\nGo, with one condition: the field training deck on Monday. Sam and I "
        "freeze the checklist tonight.\n\nLee\n",
    ),
    (
        "2026-11-19_Mark_dashboard_template.eml",
        "Mark <mark@ukpharma.example>",
        ME,
        "Shared dashboard template",
        "Thu, 19 Nov 2026 10:15:00 +0000",
        "Hi Seoyeon,\n\nThe platform team's dashboard template is here for you, Sam and Alex to "
        "reuse. Happy to walk the team through it on Wednesday.\n\nMark\n",
    ),
    (
        "2026-11-19_HR_year_end_dates.eml",
        "HR Comms <hr-comms@ukpharma.example>",
        ME,
        "Year-end review: key dates",
        "Thu, 19 Nov 2026 14:30:00 +0000",
        "Dear managers,\n\nThe review window opens on 7 December. Guidance for managers is in the "
        "HR portal.\n\nHR Comms\n",
    ),
    (
        "2026-11-20_Jo_field_training_deck.eml",
        "Jo <jo@ukpharma.example>",
        ME,
        "Field training deck",
        "Fri, 20 Nov 2026 16:45:00 +0000",
        "Hi Seoyeon,\n\nThe field training deck is ready, a little early. Both sessions are "
        "booked for the week of 30 November.\n\nJo\n",
    ),
    (
        "2026-11-20_LabViz_references.eml",
        "LabViz Sales <sales@labviz.example>",
        ME,
        "Reference customers",
        "Fri, 20 Nov 2026 11:25:00 +0000",
        "Dear Seoyeon,\n\nWe can put you in touch with two reference customers, both in "
        "regulated labs. Please tell us a good time.\n\nBest regards,\nLabViz Sales\n",
    ),
    (
        "2026-11-21_Finance_expenses_deadline.eml",
        "Priya Nair <priya.nair@ukpharma.example>",
        ME,
        "November expenses are due Friday",
        "Sat, 21 Nov 2026 08:30:00 +0000",
        "Hi all,\n\nPlease submit November expenses by Friday 27 November so they land in the "
        "next run.\n\nPriya\n",
    ),
    (
        "2026-11-22_Lee_weekend_note.eml",
        "Lee <lee@ukpharma.example>",
        ME,
        "Section four",
        "Sun, 22 Nov 2026 18:20:00 +0000",
        "Hi Seoyeon,\n\nI took section four after all, it is small. Checklist is frozen.\n\nLee\n",
    ),
]

# --------------------------------------------------------------------------- chats and recordings
CHAT_FILES: dict[str, str] = {
    "App-exports/Teams/chat-export_Seoyeon-Alex.txt": """\
Microsoft Teams - chat export: Seoyeon, Alex

[09/11/2026 09:12] Alex: Can we swap my on-call for the week of 23 Nov?
[09/11/2026 09:30] Seoyeon: Yes, agreed. Jo covers your December week.
[16/11/2026 14:02] Alex: I sent my vendor evaluation proposal by mail.
[20/11/2026 17:05] Seoyeon: Roadmap draft is late, sorry. Sending it now.
""",
    "App-exports/Teams/chat-export_team-analytics.txt": """\
Microsoft Teams - chat export: team-analytics

[10/11/2026 11:02] Jo: QBR deck v1 is in the shared folder.
[10/11/2026 11:15] Lee: Checklist v2 is ready for review.
[17/11/2026 16:40] Alex: Vendor demo is tomorrow at ten.
[19/11/2026 09:00] Seoyeon: Thanks all for sign-off. Field training deck due Monday, Jo.
[20/11/2026 16:50] Jo: Deck is ready, early.
""",
    "App-exports/Teams/2026-11-18_meeting-recap_launch-signoff.txt": """\
Microsoft Teams - meeting recap
Meeting: Launch sign-off
Date: Wednesday 18 November 2026, 14:00-15:30
Attendees: Seoyeon, Jo, Lee, Sam

Notes
- Decision: go, with one condition: the field training deck is ready on Monday.
- Risk: vendor support terms are still open.
- Checklist owner stays shared until January.

Follow-up tasks
- Jo: field training deck.
- Lee: freeze the checklist.
- Seoyeon: reply to the vendor about support terms.
""",
    "App-exports/Teams/chat-export_Seoyeon-Lee.txt": """\
Microsoft Teams - chat export: Seoyeon, Lee

[04/11/2026 11:50] Lee: Thanks for the onboarding plan, week two looks busy.
[11/11/2026 15:20] Seoyeon: How is pairing going?
[11/11/2026 15:26] Lee: Good. I would like to own section four.
[22/11/2026 18:22] Lee: Took section four, checklist frozen.
""",
    "App-exports/Slack/channel-export_team-analytics.txt": """\
Slack - channel export: #team-analytics

2026-11-03 Jo: retro notes are in the shared folder
2026-11-12 Lee: does anyone have the interview scorecard template?
2026-11-13 Alex: it is in OneDrive, Team folder
2026-11-19 Mark: shared dashboard template, see the mail
""",
    "App-exports/Zoom/2026-11-18_vendor-demo.vtt": """\
WEBVTT

00:00:05.000 --> 00:00:12.000
LabViz: Here is the dashboard with ten seats and the lab filters.

00:00:13.000 --> 00:00:20.000
Seoyeon: What is the response time for a critical issue?

00:00:21.000 --> 00:00:28.000
LabViz: Next working day on the standard plan. A 24 hour response is on the premium plan.

00:00:29.000 --> 00:00:34.000
Seoyeon: I would like two reference customers.
""",
    "App-exports/Zoom/2026-11-19_all-hands.vtt": """\
WEBVTT

00:00:04.000 --> 00:00:10.000
Director: The launch is on track. Thank you to every team.

00:00:11.000 --> 00:00:17.000
Director: The year-end review window opens on the seventh of December.

00:00:18.000 --> 00:00:23.000
Director: The January offsite invitations go out next week.
""",
}

# --------------------------------------------------------------------------- reminders, documents
REMINDER_FILES: dict[str, str] = {
    "App-exports/Reminders/team-reminders.txt": """\
Team
[x] Send Alex the on-call swap confirmation (done 11 Nov 2026)
[ ] Reply to LabViz about support terms (due 25 Nov 2026)
[ ] Send Jo QBR feedback (due 24 Nov 2026)
[ ] Confirm the venue hold with Engine Shed (due 27 Nov 2026)
Hiring
[x] Decision meeting for the analyst role (done 13 Nov 2026)
[ ] Send panel dates to Mark and Lee (due 25 Nov 2026)
[ ] Prepare data engineer interview questions (due 27 Nov 2026)
Offsite
[x] Ask Finance for the budget per head (done 16 Nov 2026)
[ ] Send the final headcount to Finance (due 20 Nov 2026)
[ ] Book the dinner table (due 4 Dec 2026)
""",
}

DOC_FILES: dict[str, str] = {
    "Documents/Work/offsite-budget-2027.csv": """\
item,planned_gbp,confirmed_gbp,note
Venue,600,600,Engine Shed main room held until 27 Nov
Catering,630,630,lunch and evening meal for 18
Workshop materials,100,80,printing and supplies
Travel,0,0,claimed separately in expenses
""",
    "Documents/Work/hiring-pipeline.csv": """\
role,stage,candidates,next_step,owner
Analyst,decision made,3,offer in progress,Seoyeon
Data engineer,phone screens,6,interviews 1 to 3 Dec,Seoyeon
""",
    "Documents/Work/vendor-comparison.csv": """\
option,cost_per_year,support,time_to_start,note
LabViz,4200,business hours (premium for 24h),two weeks,references offered
In-house,0,our own team,one quarter,two people part time
""",
    "Documents/Work/oncall-rota-2026.csv": """\
week_of,engineer,note
2026-11-02,Jo,
2026-11-09,Lee,
2026-11-16,Jo,
2026-11-23,Alex,swapped in
2026-11-30,Lee,
2026-12-07,Jo,covers Alex's December week
""",
    "Documents/Work/launch-checklist-v2.md": """\
Launch checklist v2
Wed 18 Nov 2026

1. field training deck - Jo - due Mon 23 Nov
2. runbook reviewed - Lee - done
3. vendor support terms - Seoyeon - open
4. rollback plan - Lee - done
5. communications to field teams - Jo - done
""",
    "Documents/Work/qbr-slides-outline.md": """\
QBR slides outline
Mon 16 Nov 2026

slide 1 what we shipped
slide 2 the dashboard refresh
slide 3 data quality
slide 4 what we learned
slide 5 what we need next quarter
due Mon 30 Nov 09:00
""",
    "Documents/Work/team-charter.md": """\
How the team works
Mon 5 Oct 2026

decisions are written down with an owner
we demo on Fridays
requests go through the queue, urgent ones through me
one-to-ones are never cancelled, only moved
""",
    "OneDrive - UK Pharma/Shared/ways-of-working.md": """\
Ways of working
Mon 12 Oct 2026

core hours 10:00 to 16:00
meetings have an agenda or they move
write it down, same day
""",
    "OneDrive - UK Pharma/Shared/holiday-calendar-2026.csv": """\
date,note
2026-12-25,Christmas Day
2026-12-26,Boxing Day
2027-01-01,New Year's Day
""",
    "OneDrive - UK Pharma/Shared/dashboard-template-notes.md": """\
Dashboard template (platform team)
Thu 19 Nov 2026

one layout, three chart types, the lab filters
reuse it, do not fork it
questions: ask Mark
""",
    "OneDrive - UK Pharma/Team/interview-scorecard-template.md": """\
Interview scorecard
Mon 2 Nov 2026

score 1 to 4: data judgement, explaining, curiosity, teamwork
write one example per score
same sheet for everyone
""",
    "OneDrive - UK Pharma/Team/retro-template.md": """\
Retro template
Mon 5 Oct 2026

keep, stop, start, mood
one owner per action
""",
    "Desktop/shopping-list.txt": """\
shopping
Sun 22 Nov 2026

milk, bread, coffee
dry cleaning on Tuesday
""",
    "Desktop/ideas-for-newsletter.txt": """\
ideas for the team newsletter
Fri 13 Nov 2026

a short note on the dashboard refresh
the retro in three lines
welcome Lee properly
""",
    "Downloads/reading-list.txt": """\
reading list
Sat 21 Nov 2026

The Manager's Path, chapter five
a short piece on writing decision logs
""",
    "Downloads/venue-brochure-notes.txt": """\
Engine Shed - brochure notes
Thu 12 Nov 2026

main room seats 40, projector included
kitchen available, evening hire until 22:00
""",
    "Downloads/conference-agenda-march.txt": """\
Data conference London - March 2027
Mon 9 Nov 2026

day 1: platforms and pipelines
day 2: data quality in practice (Jo's interest)
""",
}

# (title, lines) for the Word and PDF files
DOCX_FILES: dict[str, tuple[str, list[str]]] = {
    "Documents/Work/offsite-agenda.docx": (
        "Offsite agenda January 2027",
        [
            "Arrival and coffee 09:30",
            "Look back 10:00",
            "Workshop 11:00",
            "Lunch 12:30",
            "Plan for Q1 14:00",
            "Dinner 17:30",
        ],
    ),
    "Documents/Work/hiring-plan-2027.docx": (
        "Hiring plan 2027",
        [
            "Two roles: analyst and data engineer.",
            "Analyst: offer in progress.",
            "Data engineer: phone screens 30 November, interviews 1 to 3 December.",
            "Panel: manager, Mark, Jo or Lee.",
        ],
    ),
}
PDF_FILES: dict[str, tuple[str, list[str]]] = {
    "Downloads/labviz-quote-q4.pdf": (
        "LabViz quote",
        [
            "Lab dashboard, ten seats",
            "4,200 per year",
            "Support during business hours",
            "Valid until 30 November 2026",
        ],
    ),
}

# --------------------------------------------------------------------------- pictures
IMAGES_MORE: dict[str, list[str]] = {
    "Desktop/Screenshot 2026-11-16 at 10.05.12.png": [
        "Q1 roadmap sketch",
        "1 launch readiness",
        "2 dashboard decision",
        "3 training for the team",
    ],
    "Desktop/Screenshot 2026-11-18 at 15.48.30.png": [
        "LabViz price table",
        "10 seats - 4,200 a year",
        "premium support - on request",
    ],
    "Downloads/Screenshot 2026-11-19 at 17.12.44.png": [
        "Dashboard template",
        "one layout, three chart types",
        "ask Mark for the walkthrough",
    ],
    "Desktop/Screenshot 2026-11-20 at 18.02.10.png": [
        "Offsite rooms",
        "main room - workshop",
        "kitchen - lunch",
        "terrace - evening",
    ],
}

# --------------------------------------------------------------------------- calendar
WORK_EVENTS_MORE: list[tuple[str, str, str, int, tuple[str, ...]]] = [
    ("m01", "Team retro", "20261030T150000", 60, ("Sam", "Alex", "Jo", "Lee")),
    ("m02", "Team stand-up", "20261102T093000", 15, ("Sam", "Alex", "Jo", "Lee")),
    ("m03", "Weekly team meeting", "20261103T140000", 60, ("Sam", "Alex", "Jo", "Lee")),
    ("m04", "1:1 Lee", "20261104T110000", 30, ("Lee",)),
    ("m05", "Team stand-up", "20261104T093000", 15, ("Sam", "Alex", "Jo", "Lee")),
    ("m06", "Analyst panel interviews", "20261104T150000", 120, ("Mark", "Jo")),
    ("m07", "Finance check-in: offsite budget", "20261105T110000", 30, ("Priya",)),
    ("m08", "1:1 Jo", "20261105T150000", 30, ("Jo",)),
    ("m09", "Team stand-up", "20261106T093000", 15, ("Sam", "Alex", "Jo", "Lee")),
    ("m10", "Team stand-up", "20261109T093000", 15, ("Sam", "Alex", "Jo", "Lee")),
    ("m11", "Weekly team meeting", "20261110T140000", 60, ("Sam", "Alex", "Jo", "Lee")),
    ("m12", "Team stand-up", "20261111T093000", 15, ("Sam", "Alex", "Jo", "Lee")),
    ("m13", "Team stand-up", "20261113T093000", 15, ("Sam", "Alex", "Jo", "Lee")),
    ("m14", "Team stand-up", "20261116T093000", 15, ("Sam", "Alex", "Jo", "Lee")),
    ("m15", "Weekly team meeting", "20261117T140000", 60, ("Sam", "Alex", "Jo", "Lee")),
    ("m16", "1:1 Lee", "20261118T110000", 30, ("Lee",)),
    ("m17", "Team stand-up", "20261118T093000", 15, ("Sam", "Alex", "Jo", "Lee")),
    ("m18", "LabViz demo", "20261118T100000", 60, ("LabViz",)),
    ("m19", "1:1 Jo", "20261119T150000", 30, ("Jo",)),
    ("m20", "Team stand-up", "20261120T093000", 15, ("Sam", "Alex", "Jo", "Lee")),
    ("m21", "Weekly team meeting", "20261124T140000", 60, ("Sam", "Alex", "Jo", "Lee")),
    ("m22", "1:1 Lee", "20261125T110000", 30, ("Lee",)),
    ("m23", "1:1 Jo", "20261126T150000", 30, ("Jo",)),
    ("m24", "Offsite planning", "20261127T110000", 60, ("Jo", "Lee")),
    ("m25", "Team lunch", "20261127T123000", 60, ()),
    ("m26", "Phone screens: data engineer", "20261130T100000", 180, ()),
    ("m27", "Interviews: data engineer", "20261201T100000", 240, ("Mark", "Lee")),
    ("m28", "Lunch-and-learn: data quality", "20261203T123000", 60, ("Jo",)),
]

# Files whose time is not the noon of the date written in them (the generator sets the file
# time of everything else from that date, or from the date in a screenshot's name).
FILE_TIMES: dict[str, tuple[int, int, int, int, int]] = {
    f"{NOTES}/launch-signoff-notes.md": (2026, 11, 18, 15, 40),
    f"{NOTES}/field-training-notes.md": (2026, 11, 6, 16, 30),
}
