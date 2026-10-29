# START HERE: full walkthrough (about 60-90 minutes, once)

The goal of this robot: take your lead list from Google Sheets, write a short personal email to each YouTube channel,
send it slowly from your Gmail accounts, and write the result of every email back into the same sheet.

## What is new in this version
1. A blank line between "Best regards," and your signature.
2. Bullet points in the email are round circles (they are real round bullets in the HTML version, and the "•" sign in the plain-text version).
3. The email is written by ONE person. No "we", no company name, no personal name in the body. It only says your role (video editor and motion designer) and the result you bring. "Level Up VFX" appears ONLY in the signature.
4. The email focuses on what the channel may be missing and what you can bring, and it uses their YouTube channel name.
5. The greeting uses their FIRST name ("Explore with James" = James, "Muhammad Zubair" = Zubair). If no first name can be found, it says "Hi team,".
6. New sheet columns: **Sending Status**, **Sending Date** and **Reply** (plus **First Name**), so you can see what happened to every email.

## IMPORTANT: two different kinds of Gmail addresses (this is the most common confusion)
| | Where it lives | What it is |
|---|---|---|
| **Sending accounts** (your 12-15 Gmail accounts) | GitHub > Settings > Secrets > `GMAIL_ACCOUNTS` | They SEND the emails. They never go in the sheet. |
| **Lead emails** (the YouTubers you contact) | Your Google Sheet, column `Email` | They RECEIVE the emails. |

## WHERE DO THE RESULTS APPEAR?
**In the same Google Sheet, on the same tab, on the same row as the lead. The robot never creates a new tab or a new file.**
The robot adds its columns to the RIGHT of "My Notes" the first time it runs. You do not create them.

| Column (added by the robot) | What it shows |
|---|---|
| First Name | The first name used in the greeting. Blank = the email says "Hi team,". You can type a name here yourself before drafting. |
| Sender | Which of your Gmail accounts sent that email |
| **Sending Status** | Sending / Sent / Replied / Unsubscribed / Bounced / Failed |
| **Sending Date** | The day the email was sent (2026-10-27) |
| **Reply** | The first words of their reply (or "bounce"). Filled automatically when they reply |
| Sent At | Exact date and time. The robot uses it to count each account's daily limit. Do not delete it |
| Verified, Latest Video, Subject, Body, Facts, Research | Working columns (the written email is in Subject and Body) |

Your existing `Status` column keeps working as before and moves the lead along the steps (Valid > Drafted > Approved > Sent > Replied).

**Example with 5 leads:** you add 5 rows with Status `New`. After the draft run they show `Drafted` and the Subject/Body columns are filled.
You change them to `Approved`. After the send run, Status = `Sent`, Sending Status = `Sent`, Sending Date = today, Sender = the Gmail account used.
When one of them replies, within about an hour that row changes to Status `Replied`, Sending Status `Replied`, and the Reply column shows what they wrote.
(The robot only reads your inbox. Your messages stay unread.)

---------------------------------------------------------------------------------

## The tools you will use
| Tool | What it is for |
|---|---|
| Google Sheets | Your lead list (the "master file") |
| Google Cloud Console | Gives the robot permission to read and write your sheet |
| Google AI Studio | Gemini API key: the AI that writes each email |
| Gmail accounts (yours) | Send the emails. One app password each |
| GitHub | Runs the robot automatically in the cloud, free |
| Git + VS Code (on your computer) | Only used to upload this folder to GitHub |

KEYS GO IN ONE PLACE ONLY: GitHub > Settings > Secrets. Never in the sheet, never in the code files.

---------------------------------------------------------------------------------

## PART A. Your Google Sheet

1. Go to sheets.google.com. Open your master sheet. Row 1 = your header. Your data goes on the FIRST TAB (the leftmost tab).
   If your data is on another tab, you will later set a variable SHEET_TAB = that tab's exact name.
2. For every lead you want to email, set `Status` to `New` (or leave it blank). Rows with any other status are ignored.
3. Fill what you have: Email (required), Channel (the YouTube channel name, the email will use it), Niche, Subscribers, Url, Website, Notes, Pitch Angle, Score, Active.
   - The more the robot knows (Notes, Website, Url), the more personal the email.
   - If you already know the person's first name, type it into the `First Name` column. It always wins over the robot's guess.
4. Do not create the robot columns yourself. The robot adds them on its first run.

## PART B. Google Cloud: the sheet permission (15 min)

1. Go to console.cloud.google.com. Sign in with any Google account.
2. Top bar: project drop-down > New Project > name `outreach` > Create. Make sure it is selected in the top bar.
3. Left menu > APIs & Services > Library. Search "Google Sheets API" > click it > Enable.
4. (Optional) Same Library: search "YouTube Data API v3" > Enable.
5. APIs & Services > Credentials > Create credentials > Service account. Name `outreach-bot` > Create and continue > Done.
6. Click the service account in the list. Open the Keys tab > Add key > Create new key > JSON > Create. A .json file downloads. Keep it safe. Never share it.
7. Open that .json file in Notepad. Find the line `"client_email": "outreach-bot@....iam.gserviceaccount.com"`. Copy that email.
8. Go back to your Google Sheet > Share > paste that email > role **Editor** > Send.
   - Editor is required. The robot must WRITE statuses and drafts. Viewer will fail with a 403 error.
   - Do NOT share the sheet with your Gmail sending accounts. They never touch the sheet.
9. Copy the Sheet ID from the sheet's URL: docs.google.com/spreadsheets/d/**THIS_PART**/edit

(Optional) YouTube key: Credentials > Create credentials > API key. Copy it.

## PART C. Gemini key: the AI (5 min)

1. Go to aistudio.google.com > Get API key > Create API key. Copy it.
2. To use several keys (for more free daily quota), create one key per project/Google account and join them with commas:
   `key1,key2,key3`. The robot switches to the next key when one runs out.
3. Note the exact model name shown in AI Studio (example: gemini-2.5-flash). You will need it.

## PART D. Gmail app passwords (5 min per account, you have 12-15 accounts)

An app password is a special 16-LETTER password that lets the robot send from a Gmail account without your real password.
(It is 16 letters, not 16 words.) It only works if 2-Step Verification is ON. Do these steps for EACH sending account.

Tip: use a separate Chrome profile (or an incognito window) per account so you do not mix up accounts.

**Step 1: turn on 2-Step Verification**
1. Sign in to that Gmail account in the browser.
2. Go to myaccount.google.com and click **Security** in the left menu.
3. Under "How you sign in to Google" click **2-Step Verification**. Click **Get started**.
4. Add a phone number, enter the code Google sends you, then click **Turn on**. (The menu names can shift a little over time. If so, search "2-Step Verification" in the search bar at the top of the Google Account page.)

**Step 2: create the app password**
1. Go to **myaccount.google.com/apppasswords** (or search "App passwords" on the Google Account page).
2. Type a name, for example `outreach`, and click **Create**.
3. Google shows a box with 16 letters in 4 groups, like `abcd efgh ijkl mnop`.
4. **Copy it now. Google shows it only once.** Remove the spaces so it becomes `abcdefghijklmnop`.
5. Click Done. Paste it into a temporary note next to that Gmail address. Delete the note when everything works.

**If the page says "App passwords is not available for your account":**
- 2-Step Verification is not fully ON yet (finish Step 1), or
- the account uses only security keys, or has Advanced Protection, or is a work/school account where the admin blocked it.

**Step 3: IMAP (only needed for reply tracking)**
In Gmail: gear icon > See all settings > Forwarding and POP/IMAP > IMAP access = **Enable IMAP** > Save changes.
If your account no longer shows this setting, skip it.

**Good to know:** if you change that Gmail's normal password later, Google deletes its app passwords. Make a new one and update the secret.

**Step 4: write the list.** One block per account, comma between blocks, the whole thing inside [ ]. "name" is optional (it is used in the signature).
```
[{"email":"vfx.chris.ewart@gmail.com","app_password":"abcdabcdabcdabcd","name":"Chris Ewart"},
 {"email":"vfx.william.burbick@gmail.com","app_password":"efghefghefghefgh"},
 {"email":"vfx.third.person@gmail.com","app_password":"ijklijklijklijkl"}]
```
Keep going the same way up to your 12-15 accounts. Common mistakes: a missing comma between blocks, a missing quote, a space left inside the password, a comma after the LAST block.
To check it: in VS Code make a new file, paste the list, and save it as `test.json`. Red underlines show where the mistake is. Do not put this file in the project folder, and delete it afterwards.
The signature name is taken from the address: vfx.chris.ewart@gmail.com becomes "Chris Ewart".
If an address has no dots between the names (like vfxchris@gmail.com), add the "name" part.

**With 12-15 accounts:** the daily cap is PER ACCOUNT. At CAP_START 15, 15 accounts can send 225 emails on day 1, which is a lot for accounts that are new or not warmed up.
Safer for new accounts: CAP_START = 5, CAP_STEP = 1, CAP_TARGET = 30 (set in Part G).

## PART E. Install the two programs on your computer

1. Git: go to git-scm.com > Download > install, press Next on everything. (On Mac: open Terminal and type `git --version`. If it is missing, macOS offers to install it.)
2. VS Code: go to code.visualstudio.com > Download > install.
3. Unzip `outreach-bot.zip` (right-click > Extract All). You get a folder `outreach-bot`.

## PART F. Put the folder on GitHub (public)

"Public" means anyone could see your code and rules.md. That is fine: your keys, your sheet and your leads are NOT in the code, they stay private in GitHub Secrets. Public also gives you free, unlimited automation minutes.

**F1. Make the repository**
1. Go to github.com > Sign up (or sign in).
2. Top right: click the **+** > **New repository**.
3. Repository name: `outreach-bot`.
4. Choose **Public**.
5. Leave "Add a README", "Add .gitignore" and "Choose a license" all UNCHECKED. (If you tick them, the upload in F2 fails.)
6. Click **Create repository**. Keep this page open. It shows your repository address: `https://github.com/YOUR_USERNAME/outreach-bot.git`.

**F2. Upload: Option A (recommended): with Git and VS Code**
1. Open VS Code > File > Open Folder > choose the `outreach-bot` folder (the one that directly contains common.py and START_HERE.md).
2. Menu Terminal > New Terminal. A box opens at the bottom.
3. Type these ONE AT A TIME, pressing Enter after each. Replace the name, email and YOUR_USERNAME with your own:
```
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git init
git add .
git commit -m "first version"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/outreach-bot.git
git push -u origin main
```
What they do: set your name, start tracking the folder, pick all files, save a snapshot, name the branch `main`, connect to your GitHub page, and upload.
4. On the first push a browser window opens. Click **Sign in with your browser** and **Authorize**. (GitHub does not accept your normal password in the terminal. If asked for one, use the browser sign-in.)
5. Refresh the GitHub page. You should see the files, including a folder named `.github`. Open `.github` > `workflows` and check that you see three files: `draft.yml`, `replies.yml`, `send.yml`.

**F2. Upload: Option B: without Git (drag and drop in the browser)**
1. On your new empty repository page click **uploading an existing file** (or Add file > Upload files).
2. Open the `outreach-bot` folder on your computer, select EVERYTHING INSIDE it (not the folder itself), and drag it into the browser. Make sure the `.github` folder is included. On Mac it is hidden: press Cmd+Shift+. in Finder to show it.
3. Scroll down, click **Commit changes**.
4. Open `.github` > `workflows` on GitHub and confirm the three .yml files are there. If they are missing, use Option A.

**F3. Make sure it is public:** the repo page shows a "Public" label next to the name. If it says "Private": Settings > scroll to the bottom > Danger Zone > Change visibility > Public.

**Updating later (like replacing the old version with this new one):**
- Unzip the new version over your old folder (say yes to replace), then in the VS Code terminal run:
```
git add .
git commit -m "update"
git push
```
- Or, only for small text changes, open the file on GitHub (for example `rules.md`), click the pencil icon, edit, and click **Commit changes**.

## PART G. Add the keys ("APIs") to GitHub

These are called Secrets (private, nobody can read them again after saving) and Variables (settings).
On your repo page: top bar **Settings** (far right of the row: Code, Issues, ..., Settings) > left menu **Secrets and variables** > **Actions**.

**Secrets tab > "New repository secret".** Type the Name exactly (capital letters, underscores), paste the value in "Secret", click **Add secret**. Repeat for each:
| Name | Value |
|---|---|
| SHEET_ID | the Sheet ID from Part B (the long text in the sheet URL) |
| GOOGLE_SA | open the downloaded .json from Part B in Notepad, Ctrl+A, Ctrl+C, paste EVERYTHING (it starts with `{` and ends with `}`) |
| GEMINI_KEY | your Gemini key (or key1,key2,key3) |
| GMAIL_ACCOUNTS | the full list from Part D, including the [ ] brackets |
| YOUTUBE_KEY | optional |
| ZEROBOUNCE_KEY | optional (zerobounce.net, extra email checking) |

To change a secret later: click its name > Update secret (you paste the new value; the old one is never shown).

**Variables tab > "New repository variable".** Same idea, Name + Value:
| Name | Value |
|---|---|
| GEMINI_MODEL | exact model name from AI Studio |
| CAP_START_DATE | today's date, like 2026-10-27 |
| CAP_START | 15 (use 5 for new accounts) |
| CAP_STEP | 2 (use 1 for new accounts) |
| CAP_TARGET | 40 (use 30 for new accounts) |
| WRITE_LIMIT | 50 |
| AUTO_APPROVE | no |
| DRY_RUN | yes (test only) |
| IGNORE_HOURS | yes (test only) |
| POSTAL_ADDRESS | optional: your business address. US law expects one in commercial email |
| SHEET_TAB | only if your data is not on the first tab |

Then click the **Actions** tab at the top of your repo. If you see a green button "I understand my workflows, enable them", click it.

## PART H. Test with 5 rows (do not skip)

1. In the sheet add 5 rows with YOUR OWN email addresses (Gmail, Outlook, Yahoo, etc.). Status `New`, a Channel name each (try one like `Explore with James`, one like `Muhammad Zubair` and one like `Daily Frames`), and a Notes line each.
2. GitHub > **Actions** tab > left list `draft-emails` > **Run workflow** (button on the right) > green **Run workflow**. Wait for the green tick (2-5 min). Click the run to read the log. A red X means an error: click the red step to read why.
3. Refresh the sheet. New columns appear on the right. Status is now `Drafted`. Read Subject and Body.
   Check the greeting: `Hi James,` / `Hi Zubair,` / `Hi team,`. The `First Name` column shows the name used.
   If a name is wrong, fix the greeting in the Body cell by hand (you can edit Body freely while it is Drafted) and fix First Name.
4. Not happy with the wording? Edit `rules.md` (see "Where to change things"), commit, add new test rows, rerun.
5. Change Status Drafted > `Approved` on the rows you like.
6. Variables: set DRY_RUN to `no`. Actions > `send-emails` > Run workflow.
7. Check the emails arrive, in Inbox not Spam. Check: round bullets, a blank line between "Best regards," and the signature, and "Level Up VFX" only in the signature.
   In the sheet: Status `Sent`, Sending Status `Sent`, Sending Date = today, Sender filled.
8. From one test address, reply with a normal message, and from another reply `Unsub`. Run Actions > `check-replies`.
   The first row becomes `Replied` and the second `Stop` (Sending Status: Unsubscribed). The Reply column shows the text.
9. Delete the IGNORE_HOURS variable. From now on it sends only 10:00-16:00 US Eastern, Mon-Fri.

## PART I. Go live

1. Delete the 5 test rows (or change them to Stop). Add real leads with Status `New`.
2. Week 1: keep AUTO_APPROVE `no`. Each day, skim the Drafted rows (and the First Name column), then change good ones to Approved.
3. After about 20 good drafts in a row: set AUTO_APPROVE `yes`.
4. Daily job (5 min): filter Sending Status = `Replied`, answer them from Gmail. Check Review/Error rows.
5. Watch bounces. If many rows turn `Bounced`, lower CAP_TARGET and clean the list.
6. Do not sort or delete rows while a run is active (the robot protects you, but wait for the green tick).

---------------------------------------------------------------------------------

## Where to change things
| I want to change | File | How |
|---|---|---|
| What the email says, structure, tone, bullets, angles, length | `rules.md` | GitHub: open file > pencil icon > edit > Commit. Or VS Code > save > `git add .` `git commit -m "rules"` `git push` |
| Signature title, company, colour, font, "Best regards," | `settings.py` | same way |
| Signature NAME | Automatic from the Gmail address, or "name" in GMAIL_ACCOUNTS | |
| Sending speed, daily cap, hours | GitHub Variables | CAP_*, SEND_START, SEND_END, DELAY_MIN, DELAY_MAX |
| Who is emailed first | Score column | Higher first |
| Which angle | Pitch Angle column | `pain` or `missed` |
| A wrong or missing first name | `First Name` column | type it BEFORE drafting (it always wins), or fix the greeting in Body after drafting |

NOTE: the email body says you are a "video editor and motion designer", but `settings.py` signs it as "Outreach Specialist" (SIGN_TITLE).
If you want them to match, change `SIGN_TITLE` in `settings.py` to "Video Editor & Motion Designer".

## Final email layout (what leads receive)
Greeting (Hi Name, or Hi team,) > opening about their channel (channel name) > what they may be missing > what you bring (a sentence or up to 3 round bullets) > ONE question (CTA)
> Not Interested, Reply "Unsub". > Best regards, > (blank line) > Name / Outreach Specialist / Level Up VFX

## Status meanings
New/blank = waiting. Valid = email OK. Invalid = bad email. Risky = catch-all, change to Valid if you accept the risk.
Skipped = inactive. Duplicate = same email already used. Drafted = waiting for you. Review = AI draft failed checks (reason in Facts).
Approved = will send. Queued = sending now. Sent. Replied. Stop = never emailed again. Bounced. Error = send failed (reason in Facts).
Sending Status words: Sending, Sent, Replied, Unsubscribed, Bounced, Failed.

## If something breaks
| You see | Fix |
|---|---|
| Sheet is missing columns | Row 1 needs Email and Status |
| 403 / permission error on sheet | Share the sheet with the service account email as Editor |
| 535 login error | New app password. 2-Step Verification must be ON |
| Google security alert on a Gmail | Remove it from GMAIL_ACCOUNTS for a few days |
| AI error 429 | Out of free quota. Add more Gemini keys (comma separated) or lower WRITE_LIMIT |
| AI error 400/404 | Fix GEMINI_MODEL |
| Many Review rows | Read column Facts. Usually add Notes, or set MIN_FACTS = 0. "channel name missing" = the Channel cell is odd, shorten it |
| Row stuck on Queued | A run was cut off. Check that Gmail's Sent folder, then set Sent or Approved |
| Workflows stopped after 2 months | GitHub pauses idle public repos. Edit any file and commit |
| Signature name looks wrong | Add "name" for that account in GMAIL_ACCOUNTS |
| Mail goes to spam | Lower CAP_TARGET, fewer links (there are none), clean list, warm accounts longer |
| Reply column never fills | IMAP must be on (Part D, Step 3) and the account must be in GMAIL_ACCOUNTS |
| Rows say "Hi team," but a name exists | The name is only in places the robot does not read. Type it in the First Name column |

Run `python selftest.py` on your computer to test the logic offline (needs Python + `pip install -r requirements.txt`).
