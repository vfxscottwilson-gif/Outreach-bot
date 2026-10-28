import os, re, json, time

OPTOUT_LINE = 'Not Interested, Reply "Unsub".'

# YOUR master header, exactly as you gave it (28 columns). Never renamed or reordered.
MASTER = ["Niche", "Group", "Score", "Tier", "Channel", "Url", "Subscribers", "Country", "Uploads 30d",
          "Median Views", "Views To Subs", "Last Upload", "Email", "Instagram", "Website", "Socials",
          "Pitch Angle", "Min Price Usd", "Price Range", "Est Monthly Usd", "Active", "Last Checked",
          "Has Editor Credit", "Notes", "Yt Topics", "Found On", "Status", "My Notes"]

# Robot columns. The robot adds any that are missing, to the RIGHT of your last column.
BOT = ["First Name", "Sender", "Sending Status", "Sending Date", "Reply", "Sent At", "Verified",
       "Latest Video", "Subject", "Body", "Facts", "Research"]

# Plain-English label written to the "Sending Status" column whenever the robot changes Status.
# "approved" clears the label (used when a send is cancelled and the row goes back to the queue).
SEND_LABEL = {"queued": "Sending", "sent": "Sent", "bounced": "Bounced", "error": "Failed",
              "replied": "Replied", "stop": "Unsubscribed", "approved": ""}

REQUIRED = ["Email", "Status"]
EMAIL_FIND = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
NO_WORDS = {"no", "false", "0", "n", "inactive", "dead", "stopped", "closed"}
YES_WORDS = {"yes", "true", "1", "y"}


def key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def first_email(s):
    m = EMAIL_FIND.search(str(s))
    return m.group(0).lower() if m else ""


def score(r):
    try:
        return float(re.sub(r"[^\d.\-]", "", str(r.get("Score", ""))))
    except ValueError:
        return -1.0


def norm_status(v):
    return str(v).strip().lower()


def retry(fn, tries=4):
    """Retry Google Sheets calls that fail because of rate limits or short outages."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (429, 500, 502, 503) and i < tries - 1:
                time.sleep((10, 30, 60)[i])
                continue
            raise


class Sheet:
    """Reads the lead sheet once. Writes are checked against the live sheet first, so sorting,
    inserting or deleting rows while a run is going can never put data on the wrong lead."""

    def __init__(self, ws=None):
        if ws is None:
            import gspread
            try:
                gc = gspread.service_account_from_dict(json.loads(os.environ["GOOGLE_SA"]))
            except (KeyError, ValueError):
                raise SystemExit("GOOGLE_SA secret is missing or is not the full service-account JSON.")
            book = retry(lambda: gc.open_by_key(os.environ["SHEET_ID"]))
            tab = (os.getenv("SHEET_TAB") or "").strip()
            ws = book.worksheet(tab) if tab else book.sheet1
        self.ws = ws
        self._upd = []
        self.expect = {}
        self._load()

    def _load(self):
        values = retry(self.ws.get_all_values)
        if not values or not any(c.strip() for c in values[0]):
            raise SystemExit("Row 1 of the sheet is empty. Paste your header into row 1 first.")
        header = values[0]
        self.H = {}
        for i, h in enumerate(header):
            if h.strip():
                self.H.setdefault(key(h), i + 1)
        missing = [c for c in REQUIRED if key(c) not in self.H]
        if missing:
            raise SystemExit("Your sheet is missing these columns in row 1: " + ", ".join(missing))
        self._ensure_bot_cols(header)
        self.rows = []
        for i, raw in enumerate(values[1:]):
            r = {}
            for name in MASTER + BOT:
                c = self.H.get(key(name))
                r[name] = raw[c - 1].strip() if c and c - 1 < len(raw) else ""
            self.rows.append(r)
            self.expect[i + 2] = (r["Email"].lower(), norm_status(r["Status"]))

    def _ensure_bot_cols(self, header):
        missing = [c for c in BOT if key(c) not in self.H]
        if not missing:
            return
        last = max(i + 1 for i, h in enumerate(header) if h.strip())
        start, end = last + 1, last + len(missing)
        if self.ws.col_count < end:
            self.ws.add_cols(end - self.ws.col_count)
        from gspread.utils import rowcol_to_a1
        retry(lambda: self.ws.batch_update([{"range": rowcol_to_a1(1, start), "values": [missing]}],
                                           value_input_option="RAW"))
        for j, c in enumerate(missing):
            self.H[key(c)] = start + j
        print("Added robot columns:", ", ".join(missing))

    def _queue(self, n, name, value):
        from gspread.utils import rowcol_to_a1
        if key(name) not in self.H:
            return
        self._upd.append({"row": n, "name": name, "range": rowcol_to_a1(n, self.H[key(name)]),
                          "values": [[str(value)]]})
        if 0 <= n - 2 < len(self.rows):
            self.rows[n - 2][name] = str(value)

    def put(self, n, **cols):
        """put(5, Status='Valid', Sent_At='...'): underscores stand for spaces in column names.
        Whenever Status changes to Sent / Replied / Bounced / etc., "Sending Status" is updated too."""
        for k, v in cols.items():
            name = k.replace("_", " ")
            self._queue(n, name, v)
            if name == "Status" and norm_status(v) in SEND_LABEL:
                self._queue(n, "Sending Status", SEND_LABEL[norm_status(v)])

    def _letter(self, name):
        from gspread.utils import rowcol_to_a1
        return re.sub(r"\d+", "", rowcol_to_a1(1, self.H[key(name)]))

    def _live(self):
        e, s = self._letter("Email"), self._letter("Status")
        got = retry(lambda: self.ws.batch_get([f"{e}2:{e}", f"{s}2:{s}"]))
        em = [(x[0] if x else "").strip().lower() for x in got[0]]
        st = [norm_status(x[0] if x else "") for x in got[1]]
        return {i + 2: (em[i] if i < len(em) else "", st[i] if i < len(st) else "")
                for i in range(max(len(em), len(st)))}

    def flush(self):
        """Writes pending changes. Returns the set of rows that were SKIPPED because the sheet
        changed under us (row moved, email edited, or status changed by you)."""
        if not self._upd:
            return set()
        live = self._live()
        skipped, ok = set(), []
        for u in self._upd:
            n = u["row"]
            if n in skipped:
                continue
            exp = self.expect.get(n)
            if exp is not None and live.get(n, ("", "")) != exp:
                skipped.add(n)
                continue
            ok.append(u)
        if ok:
            retry(lambda: self.ws.batch_update(
                [{"range": u["range"], "values": u["values"]} for u in ok], value_input_option="RAW"))
            for u in ok:
                if u["name"] == "Status":
                    self.expect[u["row"]] = (self.expect[u["row"]][0], norm_status(u["values"][0][0]))
        if skipped:
            print(f"Skipped {len(skipped)} row(s): the sheet changed while the robot was working.")
        self._upd = []
        return skipped
