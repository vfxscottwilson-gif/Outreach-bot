# START HERE: Phase 1 (personalized emails into your Google Sheet)

WHAT IT DOES: reads your master tab, researches each lead (YouTube, website, links), writes one personal email per lead,
and adds it to a tab called **Ready to Send** (columns A to D). It sends nothing and needs no Gmail login.

Tabs in your Google file after the first run:
| Tab | Who writes it |
|---|---|
| Your master tab (leads) | You. The robot only READS it. It never changes or reorders it. |
| **Ready to Send** | The robot writes columns A-D: Email, Name, Subject, Body. You own column E onward (Date, Follow-up 1, 2, 3 ...). |
| **Log** | The robot: skipped leads, failures, and a list of every email it already wrote. |

---------------------------------------------------------------------------------

## STEP 1. Replace the old code in your repo (10 min)

1. Unzip `outreach-bot-phase1.zip`.
2. Open your existing repo folder in VS Code (File > Open Folder).
3. In the left Explorer, DELETE everything in the repo folder except the hidden `.git` folder (select all files, Delete).
   This removes the old sending workflows so nothing tries to send or fails every hour.
4. Copy everything from the unzipped folder into the repo folder. Include the `.github` folder.
5. Terminal > New Terminal, then type, one line at a time:

```
git add -A
git commit -m "phase 1: personalized emails only"
git push
```
6. On GitHub open the **Actions** tab. You should see only one workflow: **generate-emails**.

(Recommended) Make the repo **Private**: repo Settings > bottom "Danger Zone" > Change visibility > Make private.
Reason: run logs and your `rules.md` pitch stay hidden. Phase 1 uses about 5 minutes per run, far below GitHub's free private-repo allowance.
The robot never prints emails or names in its logs either way.

## STEP 2. Check your keys (5 min)

Repo > Settings > Secrets and variables > Actions.

Secrets you need (names must match exactly):
| Secret | What |
|---|---|
| SHEET_ID | the ID in your Google Sheet URL |
| GOOGLE_SA | the whole service-account JSON |
| GEMINI_KEY | your Gemini key. Several keys? `key1,key2,key3` (it switches when one is limited) |
| YOUTUBE_KEY | optional but recommended: recent video titles make emails personal |
| ANTHROPIC_API_KEY, OPENAI_API_KEY | optional extra AI backups |
| ZEROBOUNCE_KEY | optional: catches catch-all and dead mailboxes before you send |

You do NOT need GMAIL_ACCOUNTS any more. You can delete that secret.

Variables (Variables tab):
| Variable | Value |
|---|---|
| GEMINI_MODEL | exact model name from AI Studio |
| ANTHROPIC_MODEL / OPENAI_MODEL | only if you added those keys (a provider without its MODEL variable is skipped) |
| MASTER_TAB | the exact name of your master tab. SET THIS. It protects you if tabs get reordered |
| RUN_LIMIT | optional, default 25 |

## STEP 3. Prepare the Google Sheet (5 min)

1. The sheet must be shared with the service account email (the `client_email` inside the JSON) as **Editor**. The robot must write.
2. Your master tab needs row 1 headers. Required: an **Email** column. Recognised (any capitalisation):
   | Column | Names it understands |
   |---|---|
   | Email | Email, Email Address |
   | Name | First Name, Name, Contact Name, Full Name |
   | Channel | Channel, Channel Name |
   | YouTube link | Url, Channel URL, YouTube, YouTube Link |
   | Website | Website, Site, Domain |
   | Other links | Socials, Social Links, Links (Instagram, X, LinkedIn etc. are skipped because they block robots) |
   | More context | Niche, Yt Topics, Notes, Latest Video |
   | Control | Score (higher first), Active (No = skip), Status (Stop/Replied/Bounced/Sent = skip), Pitch Angle (`pain` or `missed`) |
   Never sent to the AI: prices, scores, tiers, subscribers, My Notes, Found On.
3. Put private thoughts in **My Notes**, not Notes. Notes goes to the AI.
4. You do not need to create "Ready to Send" or "Log". The robot creates them with the right headers.
   If you create "Ready to Send" yourself, row 1 must be: Email, Name, Subject, Body (then add your Date and Follow-up columns in E, F, G ...).

## STEP 4. First test (10 min)

1. GitHub > Actions > **generate-emails** > Run workflow > type `5` > Run. Wait for the green tick.
2. Open your sheet. Read the 5 rows in **Ready to Send**:
   - Name is a real first name or `Team`.
   - Subject is 45 characters or fewer.
   - Body has NO greeting, and its last line is `Best regards,`.
3. Read all 5 closely. If the style is off, edit `rules.md` once (GitHub: open file > pencil > Commit). To redo the test rows,
   delete them from BOTH tabs (Ready to Send and Log, the rows whose Result is `written`), then run again.
4. Check the **Log** tab for anything skipped or failed and why.

## STEP 5. Your daily routine

1. Run **generate-emails** with 20-30. New rows are added BELOW your old ones. Old rows are never touched.
2. Send them your way. Type the date in your Date column (E) as you send.
3. For follow-ups add columns Follow-up 1, 2, 3 ... to the right. The robot never reads or writes them.
4. Next day: run again. Only new leads get written.

Keep about 20 to 30 sends a day from a real account and raise slowly.

---------------------------------------------------------------------------------

## What the robot checks before a row is written (all in code)
- Email: valid format, domain can receive mail, not noreply/fake, not a duplicate, lowercase.
- Name: first name only. From your Name column, or found in the channel name, channel description, website, notes
  or a `first.last` email. Otherwise `Team`. "Muhammad Zubair" becomes Zubair. Never an email prefix like john123.
- Subject: 45 characters or fewer, counted in code. Too long = regenerated, then cut at a word boundary. No emoji, no ALL CAPS, no Re:/Fwd:, no spam words.
- Body: no greeting, plain text, one person ("I"), names the channel, no invented numbers or quotes, no links, ends exactly with `Best regards,` (no space or line after).
- Fact check: anything it says about the lead must exist in the data it collected.

## Real-life problems it already handles
| Problem | What happens |
|---|---|
| Run stops halfway | Rows are saved every 10 leads. Rerun continues; finished leads are skipped |
| You delete rows after sending | They are NOT regenerated (the Log remembers). To regenerate one, delete it from the Log too |
| You sort or filter Ready to Send | Safe: new rows always go below the last email in column A |
| You add Date / Follow-up columns | Never touched |
| You sort or edit the master tab | Safe: leads are matched by email, never by row number |
| Same email twice in master | Written once, duplicate logged |
| Very little data on a lead | Shorter honest email about their niche only, logged as `low data` |
| AI invents a fact, quote or number | Rejected and rewritten, up to 3 tries, then logged as failed (gives up after 3 runs) |
| AI adds Hi / sign-off / signature | Stripped in code |
| Gemini rate limit | Waits, switches key, then switches provider; if all are out it stops cleanly |
| YouTube quota | Uses only cheap calls (~2 units per lead); continues without YouTube if exhausted |
| Dead website or private links | Logged quietly, uses whatever other data exists |
| All emails sounding the same | Rotating style hints and a check that no two openings match |
| Text starting with = + - @ | Written as plain text, never as a formula |
| Master tab is not the first tab any more | Stops with a clear message (set MASTER_TAB) |
| Risky (catch-all) emails | Skipped and logged by default (protects your sending account). Set variable ALLOW_RISKY = yes to include them |

## Where to change things
| I want to change | Where |
|---|---|
| What the email says, tone, structure, bullets, offer | `rules.md` |
| Leave out the `Not Interested, Reply "Unsub".` line | Variable INCLUDE_OPTOUT = no |
| How many leads per run | Run workflow box, or variable RUN_LIMIT |
| Run automatically every day | `.github/workflows/generate.yml`: delete the `#` on the 3 schedule lines |

## If something breaks
| You see | Fix |
|---|---|
| "Cannot open the sheet" | SHEET_ID wrong, or sheet not shared with the service account as Editor |
| "no Email column" | Row 1 of the master tab needs an Email header |
| "robot tab" message | Set the MASTER_TAB variable |
| "A1:D1 is not Email, Name, Subject, Body" | Fix row 1 of Ready to Send |
| "key or model rejected" | Check the key and the exact MODEL variable |
| "AI quota used up" | Finished rows are saved. Run again later or add more keys |
| Nothing written, Log says `failed` | Read the Detail column; often add Notes or a YouTube key for richer data |
| Workflows stop after 2 months | GitHub pauses idle repos. Make any small commit |

Run `python selftest.py` on your computer to test everything offline.
