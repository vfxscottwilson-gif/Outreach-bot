# START HERE: Phase 1 (personalized emails into your Google Sheet)

`generate.py` is now ONE self-contained file. The old helper files (compose.py, llm.py, names.py, research.py,
sheetio.py, verify.py) are no longer used. You can delete them from your repo.

WHAT IT DOES: reads your master tab, researches each lead, writes one personal email per lead and adds it to the
**Ready to Send** tab (columns A to D). It sends nothing and needs no Gmail login.

| Tab | Who writes it |
|---|---|
| Master tab (default name **Main**) | You. The robot only READS it. |
| **Ready to Send** | The robot writes A-D (Email, Name, Subject, Body) below the last row. Columns E onward (Date, Follow-ups) are yours and never touched. |
| **Log** | The robot: skipped leads, failures, and a list of every email already written. |

---------------------------------------------------------------------------------

## STEP 1. Replace the code in your repo (5 min)
You need to replace TWO files (the workflow must change too, or the new key names never reach the script):
1. `generate.py`  (repo root)
2. `.github/workflows/generate.yml`

In VS Code: open your repo folder, overwrite those two files with the ones from this zip, then in the terminal:
```
git add -A
git commit -m "single-file generate.py with AI failover"
git push
```
(On github.com you can also open each file, click the pencil, paste the new content, Commit.)

## STEP 2. Keys (Settings > Secrets and variables > Actions)
Any of these spellings works. You can add several keys to one secret by separating them with commas.
| Provider | Secret name (either one) |
|---|---|
| Gemini (first choice) | GEMINI_KEY or GEMINI_API_KEY |
| Groq (backup 1) | GROQ_KEY or GROQ_API_KEY |
| OpenRouter (backup 2) | OPENROUTER_KEY or OPENROUTER_API_KEY |
| YouTube (optional) | YOUTUBE_KEY or YOUTUBE_API_KEY |
| ZeroBounce (optional) | ZEROBOUNCE_KEY or ZEROBOUNCE_API_KEY |
Required: SHEET_ID and GOOGLE_SA. You need at least ONE AI key. You do not need any Gmail secret.

**There are no model settings any more.** Give keys only. At start-up the script asks each provider which models your key can
use today, sends each a tiny test message, and uses the first ones that really answer (models with no free quota are skipped).
If you still have GitHub variables called GEMINI_MODEL, GEMINI_FALLBACK_MODELS, GROQ_MODEL or OPENROUTER_MODEL, delete them (they are ignored).

How the failover works: Gemini -> Groq -> OpenRouter. If a model is not found, a key is rejected, or a quota is used up,
the script moves on to the next model/key/provider immediately. It stops early only when EVERY provider has failed.

## STEP 3. Prepare the Sheet
1. Share the Google Sheet with the service account email (`client_email` in the JSON) as **Editor**.
2. Name your leads tab **Main** (or set the variable MASTER_TAB to its exact name). Header in row 1. Required: an Email column.
3. Recognised columns (any capitalisation): Email, Name/First Name, Channel, Url/YouTube, Website, Socials, Niche, Yt Topics,
   Notes, Latest Video, Score, Active, Status, Pitch Angle. Prices, scores, subscribers and My Notes are never sent to the AI.
4. You do not need to create "Ready to Send" or "Log". They are created automatically.
   If you create "Ready to Send" yourself, row 1 must be: Email, Name, Subject, Body.

## STEP 4. First test
1. GitHub > Actions > **generate-emails** > Run workflow > limit `5` > Run.
2. Open the run log. You should see lines like `Gemini key 1: 12 models visible; using ...` and `AI ready, in order: ...` and at the end
   `DONE. written 5 ...` with `AI calls: Gemini 5` (or Groq / OpenRouter if Gemini was unavailable).
3. Read the 5 rows in Ready to Send. If the style is off, edit `rules.md` (it is read on every run).
4. To redo test rows: delete them from Ready to Send AND the matching `written` rows in Log, then run again.

To test without writing anything, set the variable DRY_RUN = yes.

## STEP 5. Daily routine
Run generate-emails with 20-30. New rows are added below the old ones. Type your date in column E as you send.

## Variables you can set (all optional)
| Variable | Meaning |
|---|---|
| RUN_LIMIT | leads per run (the Run workflow box overrides it) |
| DRY_RUN | yes = generate and count, write nothing |
| ALLOW_RISKY | yes = also write catch-all / unverifiable emails (default no) |
| ALLOW_ROLE | no = skip info@, contact@, support@ ... (default yes = allowed) |
| INCLUDE_OPTOUT | no = leave out the `Not Interested, Reply "Unsub".` line |
| MASTER_TAB / OUTPUT_TAB / LOG_TAB | tab names |

## If something breaks
| You see in the log | Fix |
|---|---|
| No AI key found | Add GEMINI_KEY, GROQ_KEY or OPENROUTER_KEY (or the _API_KEY spelling) as a secret |
| Cannot open the sheet | SHEET_ID wrong, or sheet not shared with the service account as Editor |
| Master tab not found | Rename the tab to Main or set MASTER_TAB |
| no Email column | Row 1 of the master tab needs an Email header |
| key N: REJECTED | That key is invalid or disabled. The run continues with the other keys |
| Every AI key failed its start-up test | Keys invalid or free quota used up today. Make a fresh key at aistudio.google.com/apikey |
| Stopped early: all AI providers failed | Every key is out of quota or invalid. Finished rows are saved. Run again later or add keys |
| Failed rows in Log | Read the Detail column. Usually the lead has almost no data: add Notes or a YouTube key |

Run `python selftest.py` on your computer to test everything offline (needs `pip install gspread`).
