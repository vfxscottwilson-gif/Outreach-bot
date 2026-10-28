"""Google Sheets layer.
 - MASTER tab: read only. Nothing in this file can write to it.
 - "Ready to Send" tab: the robot only ever writes columns A to D, always BELOW the last filled row.
   Your own columns (Date, Follow-up 1, 2, 3 ...) in E onward are never read or written.
 - "Log" tab: skipped and failed leads, and a ledger of every email already written."""
import os, re, json, time, unicodedata
from datetime import datetime, timezone

HEADER = ["Email", "Name", "Subject", "Body"]
LOG_HEADER = ["Time (UTC)", "Email", "Result", "Detail"]
HEADER_OK = [{"email", "emails"}, {"name", "names", "firstname", "firstnames"},
             {"subject", "subjects", "subjectline", "subjectlines"}, {"body", "bodies"}]
EMAIL_FIND = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")

# master column name (as you might have written it) -> our field. Matching ignores case, spaces, dashes.
ALIASES = {
    "Email": ["email", "emails", "emailaddress", "contactemail", "businessemail"],
    "Name": ["firstname", "name", "contactname", "fullname", "owner", "creatorname", "person"],
    "Channel": ["channel", "channelname", "youtubechannel"],
    "Url": ["url", "channelurl", "youtubeurl", "youtubelink", "channellink", "youtube", "link"],
    "Website": ["website", "site", "websiteurl", "domain", "web"],
    "Socials": ["socials", "sociallinks", "social", "otherlinks", "links"],
    "Instagram": ["instagram", "ig"],
    "Niche": ["niche", "category", "topic"],
    "Topics": ["yttopics", "topics", "youtubetopics", "tags"],
    "Notes": ["notes", "note", "research", "facts"],
    "Latest Video": ["latestvideo", "recentvideo", "lastvideo"],
    "Score": ["score", "priority"],
    "Active": ["active"],
    "Status": ["status"],
    "Angle": ["pitchangle", "angle"],
}


def key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def first_email(s):
    m = EMAIL_FIND.search(str(s))
    return m.group(0).lower() if m else ""


def clean_cell(s):
    """Plain text only: no zero-width characters, no odd spaces, no leading formula characters."""
    s = unicodedata.normalize("NFKC", str(s)).replace("\u200b", "").replace("\ufeff", "").replace("\u00a0", " ")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s


def no_formula(s):
    while s and s[0] in "=+-@":
        s = s[1:].lstrip()
    return s


def retry(fn, tries=4):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (429, 500, 502, 503) and i < tries - 1:
                time.sleep((10, 30, 60)[i])
                continue
            raise


def score(r):
    try:
        return float(re.sub(r"[^\d.\-]", "", str(r.get("Score", ""))))
    except ValueError:
        return -1.0


class Master:
    """Read-only view of your master tab."""

    def __init__(self, ws):
        self.title = ws.title
        values = retry(ws.get_all_values)
        if not values or not any(c.strip() for c in values[0]):
            raise SystemExit(f"Row 1 of the master tab '{self.title}' is empty. Put your header in row 1.")
        H = {}
        for i, h in enumerate(values[0]):
            if h.strip():
                H.setdefault(key(h), i)
        self.col = {}
        for field, aliases in ALIASES.items():
            for a in aliases:
                if a in H:
                    self.col[field] = H[a]
                    break
        if "Email" not in self.col:
            raise SystemExit(f"Master tab '{self.title}' has no Email column. Row 1 is: "
                             + ", ".join(c for c in values[0] if c.strip()))
        self.rows = []
        for i, raw in enumerate(values[1:]):
            r = {f: (raw[c].strip() if c < len(raw) else "") for f, c in self.col.items()}
            for f in ALIASES:
                r.setdefault(f, "")
            r["_row"] = i + 2
            self.rows.append(r)


class Output:
    """The 'Ready to Send' tab. Writes columns A-D only, below the last filled row."""

    def __init__(self, ws):
        self.ws = ws

    def ensure_header(self):
        row1 = retry(lambda: self.ws.get("A1:D1"))
        row1 = (row1[0] if row1 else []) + [""] * 4
        row1 = row1[:4]
        if not any(c.strip() for c in row1):
            retry(lambda: self.ws.update(values=[HEADER], range_name="A1:D1", raw=True))
            return
        if any(key(row1[i]) not in HEADER_OK[i] for i in range(4)):
            raise SystemExit("Tab '%s' exists, but A1:D1 is not Email, Name, Subject, Body (found: %s). "
                             "Fix the header or rename that tab." % (self.ws.title, ", ".join(row1)))

    def read(self):
        """-> (set of emails already there, list of recent bodies, next free row)"""
        vals = retry(lambda: self.ws.get("A:D"))
        emails, bodies = set(), []
        for r in vals[1:]:
            em = first_email(r[0]) if r else ""
            if em:
                emails.add(em)
            if len(r) > 3 and r[3].strip():
                bodies.append(r[3])
        return emails, bodies[-150:], len(vals) + 1

    def append(self, rows):
        """rows = [[email, name, subject, body], ...]. One write call. Returns how many were written."""
        if not rows:
            return 0
        have, _, start = self.read()                      # fresh read: you may have added rows meanwhile
        rows = [r for r in rows if r[0] not in have]
        if not rows:
            return 0
        end = start + len(rows) - 1
        if end > self.ws.row_count:
            retry(lambda: self.ws.add_rows(end - self.ws.row_count + 100))
        retry(lambda: self.ws.update(values=rows, range_name=f"A{start}:D{end}", raw=True))
        back = retry(lambda: self.ws.get(f"A{start}:A{end}"))      # prove it landed where we think
        got = [first_email(r[0]) if r else "" for r in back]
        if got != [r[0] for r in rows]:
            raise SystemExit("Write check failed: rows were not found where they were written. Stopping.")
        return len(rows)


class Log:
    """The 'Log' tab. Also the memory that stops an email being written twice."""

    def __init__(self, ws):
        self.ws, self.buf = ws, []
        vals = retry(lambda: ws.get("A:D"))
        if not vals or not any(c.strip() for c in vals[0]):
            retry(lambda: ws.update(values=[LOG_HEADER], range_name="A1:D1", raw=True))
            vals = [LOG_HEADER]
        self.seen, self.fails, self.written = set(), {}, set()
        for r in vals[1:]:
            if len(r) < 3:
                continue
            em, res = first_email(r[1]) or r[1].strip().lower(), r[2].strip().lower()
            self.seen.add((em, res))
            if res == "failed":
                self.fails[em] = self.fails.get(em, 0) + 1
            if res == "written":
                self.written.add(em)
        self.next = len(vals) + 1

    def has(self, email, result):
        return (email, result.lower()) in self.seen

    def add(self, email, result, detail="", repeat=False):
        """Adds a log line once per (email, result). Failures are always added (they are counted)."""
        k = (email, result.lower())
        if k in self.seen and not repeat:
            return
        self.seen.add(k)
        if result.lower() == "failed":
            self.fails[email] = self.fails.get(email, 0) + 1
        if result.lower() == "written":
            self.written.add(email)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        self.buf.append([stamp, email, result, str(detail)[:300]])

    def flush(self):
        if not self.buf:
            return
        n = len(self.buf)
        start = self.next
        end = start + n - 1
        if end > self.ws.row_count:
            retry(lambda: self.ws.add_rows(end - self.ws.row_count + 200))
        retry(lambda: self.ws.update(values=self.buf, range_name=f"A{start}:D{end}", raw=True))
        self.next = end + 1
        self.buf = []


def open_book(book=None):
    """Returns (master_ws, output_ws, log_ws). Creates the two robot tabs if they do not exist."""
    if book is None:
        import gspread
        try:
            gc = gspread.service_account_from_dict(json.loads(os.environ["GOOGLE_SA"]))
        except (KeyError, ValueError):
            raise SystemExit("GOOGLE_SA secret is missing or is not the full service-account JSON.")
        try:
            book = retry(lambda: gc.open_by_key(os.environ["SHEET_ID"]))
        except Exception as e:
            code = getattr(getattr(e, "response", None), "status_code", "")
            raise SystemExit(f"Cannot open the sheet ({type(e).__name__} {code}). Check SHEET_ID and that the sheet is "
                             "shared with the service account email as Editor.")
    out_name = (os.getenv("OUTPUT_TAB") or "Ready to Send").strip()
    log_name = (os.getenv("LOG_TAB") or "Log").strip()
    sheets = retry(book.worksheets)
    by_title = {w.title.strip().lower(): w for w in sheets}
    want = (os.getenv("MASTER_TAB") or "").strip()
    master = by_title.get(want.lower()) if want else sheets[0]
    if master is None:
        raise SystemExit(f"MASTER_TAB '{want}' not found. Tabs: " + ", ".join(w.title for w in sheets))
    if master.title.strip().lower() in (out_name.lower(), log_name.lower()):
        raise SystemExit(f"The master tab resolved to '{master.title}', which is a robot tab. "
                         "Set the MASTER_TAB variable to the exact name of your master tab.")

    def get_or_make(name, cols):
        w = by_title.get(name.lower())
        return w or retry(lambda: book.add_worksheet(title=name, rows=1000, cols=cols))
    return master, get_or_make(out_name, 10), get_or_make(log_name, 6)
